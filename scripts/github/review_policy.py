"""A bot-authored release PR still needs a DIFFERENT human's approval.

Trusted workflow code is always checked out from main. No PR code is executed.
The initiating human is read from GitHub's workflow-run API, not a PR-controlled
actor field. Team membership alone is insufficient: accepted write access is checked.
"""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


class GitHub:
    def __init__(self, repository):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('Invalid repository')
        self.repo = repository

    def api(self, endpoint, *, method='GET', payload=None):
        args = ['gh', 'api', '--method', method, 'repos/' + self.repo + '/' + endpoint]
        with tempfile.TemporaryDirectory(prefix='final-review-') as temporary:
            if payload is not None:
                path = Path(temporary) / 'request.json'
                path.write_text(json.dumps(payload), encoding='utf-8')
                args += ['--input', str(path)]
            result = subprocess.run(args, capture_output=True, encoding='utf-8', check=True)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def pages(self, endpoint):
        items = []
        for page in range(1, 101):
            separator = '&' if '?' in endpoint else '?'
            value = self.api(endpoint + separator + f'per_page=100&page={page}')
            if not isinstance(value, list):
                raise ValueError('Expected paginated list')
            items.extend(value)
            if len(value) < 100:
                return items
        raise ValueError('Review list exceeds supported pagination; manual review required')


def evaluate(api, number, team):
    pr = api.api('pulls/' + str(number))
    sha = pr['head']['sha']
    if not re.fullmatch(r'[a-f0-9]{40}', sha):
        raise ValueError('Invalid PR head SHA')
    if pr['base']['ref'] != 'main':
        return sha, 'failure', 'Unexpected deployment target branch'
    if pr['state'] != 'open':
        return sha, 'neutral', 'Pull request is no longer open'
    files = api.pages(f'pulls/{number}/files')
    is_release = any(f['filename'] == 'deploy/release.json' for f in files)
    if not is_release:
        return sha, 'success', 'Source PR: GitHub branch protection requires another reviewer'
    content = api.api('contents/deploy/release.json?ref=' + sha)
    data = json.loads(base64.b64decode(content['content']).decode())
    run_id = str(data.get('runId', ''))
    if not re.fullmatch(r'[1-9][0-9]*', run_id):
        return sha, 'failure', 'Release has no trusted image workflow run'
    run = api.api('actions/runs/' + run_id)
    if (run.get('head_branch') != 'main' or run.get('path', '').split('@')[0] != '.github/workflows/build-push.yml'
            or run.get('repository', {}).get('full_name', '').lower() != api.repo.lower()):
        return sha, 'failure', 'Images were not produced by the trusted main workflow'
    if run.get('status') != 'completed':
        return sha, 'pending', 'Image workflow is still finishing'
    if run.get('conclusion') != 'success':
        return sha, 'failure', 'Image workflow did not succeed'
    if data.get('intent') == 'release':
        updated = data.get('updatedServices', [])
        if not updated or any(data.get('images', {}).get(service, {}).get('source') != run.get('head_sha') for service in updated):
            return sha, 'failure', 'Release image sources do not match the trusted workflow'
    actor = run.get('actor', {}).get('login', '').lower()
    triggering = run.get('triggering_actor', {}).get('login', actor).lower()
    forbidden = {actor, triggering, pr['user']['login'].lower()}
    eligible = {name.lower() for name in [team['owner'], *team['collaborators']]}
    latest = {}
    for review in sorted(api.pages(f'pulls/{number}/reviews'), key=lambda r: r['id']):
        state = review['state']
        if state != 'COMMENTED':
            latest[review['user']['login'].lower()] = review
    for login, review in latest.items():
        if (login not in eligible or login in forbidden or review['state'] != 'APPROVED'
                or review.get('commit_id') != sha):
            continue
        permission = api.api('collaborators/' + login + '/permission').get('permission')
        if permission in ('write', 'maintain', 'admin'):
            return sha, 'success', 'Approved by another authorized teammate: ' + login
    return sha, 'pending', 'Waiting for a current-head approval from another teammate with accepted write access'


def publish_check(api, sha, conclusion, title):
    if not re.fullmatch(r'[a-f0-9]{40}', sha):
        raise ValueError('Invalid check SHA')
    payload = {'name': 'release-approval', 'head_sha': sha,
               'status': 'in_progress' if conclusion == 'pending' else 'completed',
               'output': {'title': title, 'summary': 'Peer approval is separate from CI execution permission. No AWS operation was performed.'}}
    if conclusion != 'pending':
        payload['conclusion'] = conclusion
    # A previous run may belong to a superseded Actions check suite. Updating
    # that check leaves it outside the PR's current rollup. Publish this freshly
    # evaluated decision in the current invocation; never reuse an old suite.
    return api.api('check-runs', method='POST', payload=payload)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pr', type=int, required=True)
    args = parser.parse_args()
    if args.pr < 1:
        raise ValueError('Invalid PR number')
    team = json.loads((ROOT / 'scripts/github/team.json').read_text(encoding='utf-8'))
    api = GitHub(team['repository'])
    try:
        sha, conclusion, title = evaluate(api, args.pr, team)
    except Exception:
        # Fail closed even if API validation/pagination is unavailable.
        pr = api.api('pulls/' + str(args.pr))
        publish_check(api, pr['head']['sha'], 'failure', 'Review policy could not be verified; inspect workflow logs')
        raise
    publish_check(api, sha, conclusion, title)
    print(conclusion + ': ' + title)


if __name__ == '__main__':
    main()
