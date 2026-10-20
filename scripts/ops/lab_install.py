"""Install/resume a lab, or adopt an approved main release after initial bootstrap.

Initial installation pins the tested release PR's immutable commit into an EMPTY
cluster. It never merges/bypasses a PR. PromoteMain later switches GitOps to main
only after that baseline is merged through the protected branch review policy.
"""
import argparse
import base64
from datetime import datetime
import getpass
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import uuid

from lab_common import (CONFIG, ROOT, STATE_BUCKET, Journal, Runner, CommandError, APP_NAMES,
                        apply_plan, check_identity, clear_runtime_secrets, cluster, confirm,
                        connect, ensure_revision, infra_variables, k8s_variables, load_settings,
                        managed, now, preflight, prepare_secrets, public_ip, save_json, state)

STAGES = ('ses', 'bootstrap', 'infra', 'connect', 'tools', 'admin', 'images', 'apps', 'dns-mail', 'verify')


def ensure_ses(runner, settings, *, timeout=1800, clock=time.monotonic, sleep=time.sleep):
    addresses = set(settings[key] for key in ('senderEmail', 'testRecipientEmail', 'adminEmail'))
    for address in sorted(addresses):
        try:
            runner.aws('sesv2', 'get-email-identity', '--email-identity', address)
        except CommandError as error:
            if error.aws_code != 'NotFoundException':
                raise
            runner.aws('sesv2', 'create-email-identity', '--email-identity', address)
            print('SES verification requested. Open the AWS verification email for your configured address.', flush=True)
    deadline = clock() + timeout
    while True:
        statuses = [runner.aws('sesv2', 'get-email-identity', '--email-identity', address)
                    .get('VerifiedForSendingStatus', False) for address in sorted(addresses)]
        if all(statuses):
            print('SES sender, buyer test address and administrator are verified.', flush=True)
            return
        if clock() >= deadline:
            raise TimeoutError('SES verification pending; click the email link and rerun Install-Lab.ps1 -Execute')
        print('WAIT: SES verification email links (Ctrl+C is safe; rerun to resume)', flush=True)
        sleep(15)


def bootstrap_state(runner, directory, approved):
    runner.tf('terraform-state-bootstrap', 'init', '-input=false', '-no-color')
    buckets = runner.aws('s3api', 'list-buckets')['Buckets']
    if STATE_BUCKET in {b['Name'] for b in buckets}:
        tags = runner.aws('s3api', 'get-bucket-tagging', '--bucket', STATE_BUCKET,
                          '--expected-bucket-owner', CONFIG['account'])['TagSet']
        tags = {t['Key']: t['Value'] for t in tags}
        if tags.get('Project') != 'Final' or tags.get('Purpose') != 'TerraformState':
            raise ValueError('Existing state bucket ownership tags do not match this project')
        # A new school checkout has no bootstrap local state. Adopt only the exact,
        # owner-checked project bucket, never create a second competing state root.
        try:
            tracked = set(runner.tf('terraform-state-bootstrap', 'state', 'list').splitlines())
        except CommandError as error:
            if 'No state file was found' not in error.stderr:
                raise
            tracked = set()
        for resource in ('aws_s3_bucket.state', 'aws_s3_bucket_versioning.state',
                         'aws_s3_bucket_server_side_encryption_configuration.state',
                         'aws_s3_bucket_public_access_block.state', 'aws_s3_bucket_ownership_controls.state',
                         'aws_s3_bucket_policy.state'):
            if resource not in tracked:
                runner.tf('terraform-state-bootstrap', 'import', '-input=false', resource, STATE_BUCKET)
    apply_plan(runner, 'terraform-state-bootstrap', 'bootstrap', {'state_bucket_name': STATE_BUCKET},
               approved=approved, directory=directory)


def prepare_admin(runner, email, password_reader=getpass.getpass):
    try:
        existing = runner.kube('get', 'secret', 'final-admin-config', '-n', CONFIG['namespace'])
    except CommandError as error:
        if 'NotFound' not in error.stderr and 'not found' not in error.stderr:
            raise
        existing = None
    if existing:
        current = base64.b64decode(existing.get('data', {}).get('admin-email', '')).decode()
        if current == email and existing.get('data', {}).get('admin-password'):
            print('Reusing existing administrator Secret; no password change.', flush=True)
            return
        raise ValueError('Administrator Secret already exists with another email; review it before changing an existing account')
    password = password_reader('Administrator password (12..64 characters, hidden): ')
    if not 12 <= len(password) <= 64:
        raise ValueError('Administrator password must contain 12..64 characters')
    if password_reader('Confirm administrator password (hidden): ') != password:
        raise ValueError('Administrator passwords differ')
    payload = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
               'metadata': {'name': 'final-admin-config', 'namespace': CONFIG['namespace']},
               'data': {'admin-email': base64.b64encode(email.encode()).decode(),
                        'admin-password': base64.b64encode(password.encode()).decode()}}
    try:
        runner.run(['kubectl', 'apply', '--server-side', '--field-manager=final-admin-setup', '-f', '-'],
                   input_text=json.dumps(payload))
    finally:
        payload = None
        password = None
    print('Administrator Secret prepared; password is not saved in the local config.', flush=True)


def source_revision(runner):
    if runner.run(['git', 'status', '--porcelain', '--untracked-files=normal']):
        raise ValueError('Commit/stash local code edits first; generated .lab files are ignored')
    sha = ensure_revision(runner.run(['git', 'rev-parse', 'HEAD']))
    remote = runner.run(['git', 'ls-remote', 'https://github.com/' + CONFIG['repository'] + '.git', 'refs/heads/main']).split()
    if not remote or remote[0] != sha:
        raise ValueError('Checkout must match current main; run git switch main and git pull --ff-only origin main')
    return sha


def wait_image_release(runner, journal, source, *, timeout=2400, clock=time.monotonic, sleep=time.sleep):
    details = journal.data['details']
    if not details.get('imageRequest'):
        details['imageRequest'] = 'lab-' + uuid.uuid4().hex
        journal.save()  # Save correlation before dispatch so a timeout cannot publish twice blindly.
    request = details['imageRequest']
    title = 'Lab build ' + request
    deadline = clock() + timeout
    dispatched = details.get('imageDispatchAttempted', False)
    while True:
        runs = runner.json(['gh', 'run', 'list', '--repo', CONFIG['repository'], '--workflow', 'build-push.yml',
                            '--event', 'workflow_dispatch', '--branch', 'main', '--limit', '100',
                            '--json', 'databaseId,headSha,displayTitle,status,conclusion'])
        matches = [r for r in runs if r['displayTitle'] == title]
        if matches:
            run = max(matches, key=lambda r: r['databaseId'])
            if run['headSha'] != source:
                raise ValueError('main changed before image build; refuse a mixed-source install')
            details['imageRun'] = run['databaseId']
            journal.save()
            if run['status'] == 'completed':
                if run['conclusion'] != 'success':
                    raise RuntimeError(f"Image run {run['databaseId']} did not succeed; fix/re-run that workflow, then resume")
                break
        elif not dispatched:
            details['imageDispatchAttempted'] = True
            journal.save()
            runner.run(['gh', 'workflow', 'run', 'build-push.yml', '--repo', CONFIG['repository'], '--ref', 'main',
                        '-f', 'full_build=true', '-f', 'publish_images=true', '-f', 'request_id=' + request])
            dispatched = True
            details['imageDispatched'] = True
            journal.save()
        if clock() >= deadline:
            raise TimeoutError('Image build wait timed out; rerun the same installer to resume (no duplicate dispatch)')
        print('WAIT: tested images / release proposal ' + str(details.get('imageRun', request)), flush=True)
        sleep(15)
    prefix = 'release/' + source[:12] + '-' + str(details['imageRun']) + '-'
    prs = runner.json(['gh', 'pr', 'list', '--repo', CONFIG['repository'], '--state', 'all', '--limit', '100',
                       '--json', 'number,url,headRefName,headRefOid,state'])
    proposals = [p for p in prs if p['headRefName'].startswith(prefix)]
    if len(proposals) != 1:
        raise ValueError('Expected one release proposal for this exact image run')
    proposal = proposals[0]
    if proposal['state'] == 'CLOSED':
        raise ValueError('Release PR was closed without merge; review before deployment')
    revision = ensure_revision(proposal['headRefOid'])
    runner.run(['git', 'fetch', 'origin', proposal['headRefName']])
    if runner.run(['git', 'rev-parse', 'FETCH_HEAD']) != revision:
        raise ValueError('Release branch changed while preparing install')
    runner.run(['git', 'merge-base', '--is-ancestor', source, revision])
    changed = set(runner.run(['git', 'diff', '--name-only', source, revision]).splitlines())
    if changed != {'app/msa/kustomization.yaml', 'deploy/release.json'}:
        raise ValueError('Bootstrap proposal contains changes beyond the tested image declarations')
    declaration = runner.json(['git', 'show', revision + ':deploy/release.json'])
    validate_images(runner, declaration)
    details.update(releaseRevision=revision, releasePr=proposal['number'], releaseUrl=proposal['url'])
    journal.save()
    print('Initial install uses the tested immutable release commit. PR is NOT auto-merged: ' + proposal['url'], flush=True)


def validate_images(runner, declaration):
    from update_image_tags import IMAGES  # scripts/ci is added by main, not an installed dependency.
    if set(declaration.get('images', {})) != {'member', 'product', 'ordering', 'apigateway', 'frontend'}:
        raise ValueError('Expected all five tested images')
    for service, value in declaration['images'].items():
        digest = value.get('digest', '')
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
            raise ValueError('Invalid image digest')
        images = runner.aws('ecr', 'batch-get-image', '--repository-name', IMAGES[service],
                            '--image-ids', 'imageDigest=' + digest)
        if images.get('failures') or len(images.get('images', [])) != 1:
            raise ValueError('Required image is absent from ECR: ' + service)


def fresh_or_same_install(runner, journal, revision):
    deployments = runner.kube('get', 'deployments', '-n', 'soldesk')['items']
    apps = runner.kube('get', 'applications', '-n', 'argocd')['items']
    app = next((a for a in apps if a['metadata']['name'] == 'final-apps'), None)
    if deployments and (not app or app['spec']['source']['targetRevision'] != revision):
        raise ValueError('Existing service found: bootstrap approval exception cannot redeploy an existing environment')


def install(runner, settings, journal, directory, approved=False, config_path=None):
    source = source_revision(runner)
    if journal.data.get('source') and journal.data['source'] != source:
        raise ValueError('Source changed since checkpoint; finish/review this run before starting another source revision')
    journal.data['source'] = source
    signature = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
    details = journal.data['details']
    if details.get('settingsFingerprint') not in (None, signature):
        raise ValueError('Settings changed during install; review the checkpoint before resuming')
    details['settingsFingerprint'] = signature
    live = cluster(runner)
    if live and not details.get('vpc'):
        created = str(live.get('createdAt', ''))
        if (not details.get('startedWithoutCluster') or not created or
                datetime.fromisoformat(created.replace('Z', '+00:00')) < datetime.fromisoformat(journal.data['startedAt'])):
            raise ValueError('Existing cluster has no matching install checkpoint; refuse to disable/rebootstrap a live service')
    elif not live and 'infra' not in journal.data['completed']:
        details['startedWithoutCluster'] = True
    if 'cidr' not in details:
        details['cidr'] = public_ip()
    journal.save()
    # A completed infra stage must refer to the SAME live build, never yesterday's cluster.
    if 'infra' in journal.data['completed']:
        live = cluster(runner)
        if not live or live['resourcesVpcConfig']['vpcId'] != details.get('vpc'):
            raise ValueError('Checkpoint is stale or refers to a deleted/recreated cluster')
    journal.stage('ses', lambda: ensure_ses(runner, settings))
    journal.stage('bootstrap', lambda: bootstrap_state(runner, directory, approved))

    def infrastructure():
        runner.tf('terraform', 'init', '-input=false', '-no-color')
        apply_plan(runner, 'terraform', 'infra', infra_variables(settings, details['cidr']), approved=approved, directory=directory)
        live = cluster(runner)
        if not live:
            raise ValueError('Terraform completed without expected cluster')
        details['vpc'] = live['resourcesVpcConfig']['vpcId']
        journal.save()
        runner.run([sys.executable, 'scripts/ops/verify_lab.py', 'infra', '--report', str(directory / 'infra-check.json')])
    journal.stage('infra', infrastructure)
    journal.stage('connect', lambda: connect(runner, directory), always=True)

    def tools():
        prepare_secrets(runner)
        runner.tf('terraform-k8s', 'init', '-input=false', '-no-color')
        apply_plan(runner, 'terraform-k8s', 'tools', k8s_variables(), approved=approved, directory=directory)
        runner.run([sys.executable, 'scripts/ops/verify_lab.py', 'tools', '--report', str(directory / 'tools-check.json')])
    journal.stage('tools', tools)
    journal.stage('admin', lambda: prepare_admin(runner, settings['adminEmail']))

    def images():
        role = json.loads(runner.tf('terraform', 'output', '-json', 'github_actions_role_arn'))
        runner.run(['gh', 'variable', 'set', 'AWS_ROLE_TO_ASSUME', '--repo', CONFIG['repository'], '--body', role])
        wait_image_release(runner, journal, source)
    journal.stage('images', images)
    revision = ensure_revision(details['releaseRevision'])

    def applications():
        fresh_or_same_install(runner, journal, revision)
        prepare_secrets(runner)
        apply_plan(runner, 'terraform-k8s', 'apps', k8s_variables(revision, active=True), approved=approved, directory=directory)
        wait_alb(runner, directory)
    journal.stage('apps', applications)

    def endpoints():
        ensure_ses(runner, settings)
        apply_plan(runner, 'terraform', 'dns-mail', infra_variables(settings, details['cidr'], dns=True, mail=True),
                   approved=approved, directory=directory)
    journal.stage('dns-mail', endpoints)

    def verify():
        runner.run([sys.executable, 'scripts/ops/lab_verify.py', '--revision', revision, '--manifest-ref', revision,
                    '--config', str(config_path or ROOT / '.lab/lab-config.json'),
                    '--report', str(directory / 'verification.json')], timeout=1200)
    journal.stage('verify', verify, always=True)
    print('\nREADY: initial infrastructure and service checks passed.', flush=True)
    print('Initial GitOps revision is pinned. Before future automatic main deployments, have a teammate approve/merge ' + details['releaseUrl'], flush=True)
    print('Then run: .\\Install-Lab.ps1 -Execute -PromoteMain (approval is NOT bypassed).', flush=True)
    print('Confirm the operations SNS email subscription in your inbox; real order-mail delivery remains a functional test.', flush=True)


def wait_alb(runner, directory, *, timeout=600, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + timeout
    while True:
        try:
            runner.run([sys.executable, 'scripts/ops/verify_lab.py', 'load-balancers', '--report', str(directory / 'alb-check.json')])
            return
        except CommandError:
            if clock() >= deadline:
                raise TimeoutError('ALB/target health not ready; inspect .lab/runtime/alb-check.json')
            print('WAIT: ALB targets becoming healthy', flush=True)
            sleep(15)


def promote_main(runner, settings, journal, directory, approved=False, config_path=None):
    details = journal.data['details']
    baseline = details.get('releasePr')
    if not baseline:
        raise ValueError('Missing bootstrap checkpoint/release PR; do not guess a deployment baseline')
    review = runner.json(['gh', 'pr', 'view', str(baseline), '--repo', CONFIG['repository'], '--json', 'state,mergedAt'])
    if review['state'] != 'MERGED':
        raise ValueError('Bootstrap release PR must be approved/merged first; this script never bypasses approval')
    protection = runner.json(['gh', 'api', 'repos/' + CONFIG['repository'] + '/branches/main/protection'])
    contexts = set(protection.get('required_status_checks', {}).get('contexts', []))
    if (not protection.get('enforce_admins', {}).get('enabled') or
            protection.get('required_pull_request_reviews', {}).get('required_approving_review_count', 0) < 1 or
            not {'required-ci', 'release-approval'} <= contexts):
        raise ValueError('main approval protection must be active before automatic production updates')
    runner.run(['git', 'fetch', 'origin', 'main'])
    sha = ensure_revision(runner.run(['git', 'rev-parse', 'origin/main']))
    declaration = runner.json(['git', 'show', sha + ':deploy/release.json'])
    validate_images(runner, declaration)
    connect(runner, directory)
    administrator = runner.kube('get', 'secret', 'final-admin-config', '-n', CONFIG['namespace'])
    if base64.b64decode(administrator.get('data', {}).get('admin-email', '')).decode() != settings['adminEmail']:
        raise ValueError('Administrator email changed in config; explicitly update/review the account Secret before changing notification routing')
    apply_plan(runner, 'terraform', 'update-infra', infra_variables(settings, public_ip(), dns=True, mail=True),
               approved=approved, directory=directory)
    prepare_secrets(runner)
    # Preserve initial enable flags and switch the GitOps source to protected main.
    apply_plan(runner, 'terraform-k8s', 'promote-main', k8s_variables('main', active=True), approved=approved, directory=directory)
    runner.run([sys.executable, 'scripts/ops/lab_verify.py', '--revision', sha, '--manifest-ref', sha,
                '--config', str(config_path or ROOT / '.lab/lab-config.json'),
                '--report', str(directory / 'promote-check.json')], timeout=1200)
    details['mainAdopted'] = sha
    journal.save()
    runner.run(['gh', 'variable', 'set', 'ENABLE_IMAGE_PUBLISH', '--repo', CONFIG['repository'], '--body', 'true'])
    print('READY: Argo CD follows protected main; future release PR merges are deployed automatically.', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--approve-plans', action='store_true')
    parser.add_argument('--promote-main', action='store_true')
    parser.add_argument('--config', type=Path, default=ROOT / '.lab/lab-config.json')
    args = parser.parse_args()
    if not args.execute:
        print('PREVIEW ONLY. Install stages: ' + ' -> '.join(STAGES))
        print('Run .\\Install-Lab.ps1 -Execute. AWS costs: EKS, t3.medium nodes (start 3/max 6), RDS, NAT and storage.')
        return
    runner = Runner()
    directory = ROOT / '.lab/runtime'
    directory.mkdir(parents=True, exist_ok=True)
    try:
        preflight(runner)
        settings = load_settings(args.config, create=True, identity=check_identity(runner))
        journal = Journal(ROOT / '.lab/install-state.json', 'install')
        if journal.data.get('closed'):
            archive = ROOT / '.lab/archive' / ('install-' + uuid.uuid4().hex + '.json')
            save_json(archive, journal.data)
            journal.path.unlink()
            journal = Journal(journal.path, 'install')
        if args.promote_main:
            promote_main(runner, settings, journal, directory, args.approve_plans, args.config.resolve())
        else:
            install(runner, settings, journal, directory, args.approve_plans, args.config.resolve())
    finally:
        clear_runtime_secrets(runner)


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT / 'scripts/ci'))
    try:
        main()
    except KeyboardInterrupt:
        print('\nSTOPPED: checkpoint kept. Run the same command to resume.', file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        sys.exit(1)
