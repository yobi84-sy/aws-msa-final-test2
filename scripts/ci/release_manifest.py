"""이미지를 다시 빌드하지 않고 게시하고, 승인 대상 배포 선언만 PR로 제안합니다."""
import argparse
import gzip
import json
import os
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).parent))
from changed_services import select, SERVICES, diff_paths
from update_image_tags import update, IMAGES
MANIFEST=Path('app/msa/kustomization.yaml')
RELEASE=Path('deploy/release.json')
REGISTRY='021158485482.dkr.ecr.ap-northeast-2.amazonaws.com'
def run(*args):
    return subprocess.check_output(args,text=True,encoding="utf-8").strip()
def pin(text, service, sha, digest):
    if not re.fullmatch(r'sha256:[a-f0-9]{64}',digest): raise ValueError('Invalid digest')
    text=update(text,[service],sha)
    pattern=r'(^  - name: '+re.escape(REGISTRY+'/'+IMAGES[service])+r'\n    newTag: [^\n]+)(?:\n    digest: [^\n]+)?'
    text,count=re.subn(pattern,lambda m:m[1]+'\n    digest: '+digest,text,flags=re.M)
    if count!=1: raise ValueError('Missing image')
    return text
def validate(base):
    if not RELEASE.exists(): return
    data=json.loads(RELEASE.read_text(encoding='utf-8'))
    if data.get('intent') not in ('release','rollback'): raise ValueError('Invalid release intent')
    text=MANIFEST.read_text(encoding='utf-8')
    for service,item in data['images'].items():
        if service not in SERVICES or not re.fullmatch(r'[a-f0-9]{40}',item['source']): raise ValueError('Invalid source')
        if not re.fullmatch(r'sha256:[a-f0-9]{64}',item['digest']): raise ValueError('Invalid image digest')
        if pin(text,service,item['source'],item['digest'])!=text: raise ValueError('Release/image mismatch')
    # 배포 선언 변경 PR에서만 오래된 빌드를 검사한다. 일반 소스 PR은 새 코드 변경이 목적이다.
    if not base or set(base)=={'0'}: return
    paths=diff_paths(base,'HEAD')
    if 'deploy/release.json' in paths and not select(paths) and data['intent']=='release':
        for service in data.get('updatedServices',[]):
            if service in select(diff_paths(data['images'][service]['source'],base)):
                raise ValueError('Source changed after build; rebuild release')
def publish():
    services=json.loads(os.environ['SERVICES_JSON']);sha=os.environ['GITHUB_SHA']
    data=json.loads(RELEASE.read_text(encoding='utf-8')) if RELEASE.exists() else {'images':{}}
    text=MANIFEST.read_text(encoding='utf-8')
    for service in services:
        if service not in SERVICES: raise ValueError('Invalid service')
        # Actions artifact는 지정한 서비스 디렉터리만 읽고, 검사한 docker save 산출물을 그대로 게시한다.
        with gzip.open(Path('images')/('image-'+service)/'image.tar.gz','rb') as source, open('image.tar','wb') as target:
            import shutil;shutil.copyfileobj(source,target)
        subprocess.run(['docker','load','-i','image.tar'],check=True)
        repo=IMAGES[service];image=f'{REGISTRY}/{repo}:{sha}'
        subprocess.run(['docker','tag','local-check:'+service,image],check=True)
        subprocess.run(['docker','push',image],check=True)
        raw=run('aws','ecr','batch-get-image','--region','ap-northeast-2','--repository-name',repo,'--image-ids','imageTag='+sha,'--output','json')
        result=json.loads(raw)
        if result.get('failures') or len(result['images'])!=1: raise ValueError('ECR image lookup failed')
        digest=result['images'][0]['imageId']['imageDigest']
        text=pin(text,service,sha,digest);data['images'][service]={'source':sha,'digest':digest}
    data.update(intent='release',updatedServices=services,runId=os.environ['GITHUB_RUN_ID'])
    RELEASE.parent.mkdir(exist_ok=True);RELEASE.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    MANIFEST.write_text(text,encoding='utf-8')
def propose():
    sha=os.environ['GITHUB_SHA'];repo=os.environ['GITHUB_REPOSITORY'];branch='release/'+sha[:12]+'-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']
    if run('git','ls-remote','origin','refs/heads/main').split()[0]!=sha: raise ValueError('Main changed; refuse stale release PR')
    run('git','switch','-c',branch);run('git','config','user.name','github-actions[bot]');run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    run('git','add',str(MANIFEST),str(RELEASE));run('git','commit','-m','Propose reviewed deployment '+sha)
    # App token은 URL이나 명령 인수에 넣지 않고 Git credential helper 환경에서만 사용한다.
    helper='credential.helper=!f() { echo username=x-access-token; echo "password=$GH_TOKEN"; }; f'
    run('git','-c','http.https://github.com/.extraheader=','-c','credential.helper=','-c',helper,'push','origin','HEAD:refs/heads/'+branch)
    body=Path('/tmp/release-pr.md')
    body.write_text(f'## 배포 변경\n소스: `{sha}`\n\n테스트한 이미지 산출물을 그대로 ECR에 게시하고 digest로 고정했습니다.\n\n- [ ] 변경 서비스·이미지·DB 호환성 검토\n- [ ] 다른 팀원 승인\n- [ ] 병합 후 deploy-check 결과 확인\n\n복구: scripts/ops/rollback_release.py로 이전 배포 PR을 제안합니다. DB/인프라는 자동으로 되돌리지 않습니다.\n',encoding='utf-8')
    url=run('gh','pr','create','--repo',repo,'--base','main','--head',branch,'--title','배포 승인 요청: '+sha[:12],'--body-file',str(body))
    number=re.search(r'/pull/([1-9][0-9]*)$',url)
    if not number: raise ValueError('Could not identify created release PR')
    # GITHUB_TOKEN PR events do not recursively trigger Actions. Explicit dispatch
    # is supported and places required-ci on the release head without AWS writes.
    if not os.environ.get('RELEASE_APP_ID'):
        run('gh','workflow','run','build-push.yml','--repo',repo,'--ref',branch,
            '-f','full_build=false','-f','publish_images=false')
    # Bot-created events may not trigger workflows. This trusted main workflow
    # posts the peer-review gate; CI permission approval is not deployment approval.
    run('gh','workflow','run','review-policy.yml','--repo',repo,'--ref','main',
        '-f','pr_number='+number[1])
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['publish','propose','validate']);parser.add_argument('--base',default='');args=parser.parse_args()
    {'publish':publish,'propose':propose,'validate':lambda:validate(args.base)}[args.command]()
