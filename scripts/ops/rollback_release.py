"""이전 이미지 선언을 별도 브랜치/PR로 복구합니다. main 직접 push와 kubectl 변경은 하지 않습니다."""
import argparse
import json
import re
import subprocess
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ci'))
from release_manifest import pin, MANIFEST, RELEASE, IMAGES
def git(*args):return subprocess.check_output(['git',*args],text=True,encoding="utf-8").strip()
def main():
    p=argparse.ArgumentParser();p.add_argument('--release-commit',required=True);args=p.parse_args();sha=args.release_commit
    if not re.fullmatch(r'[a-f0-9]{40}',sha):raise ValueError('Full Git commit SHA required')
    if git('status','--porcelain'):raise ValueError('Commit/stash local changes first')
    git('fetch','origin','main');git('merge-base','--is-ancestor',sha,'origin/main')
    previous=json.loads(git('show',sha+':deploy/release.json'))
    if set(previous.get('images',{})) != set(IMAGES):raise ValueError('Full five-service release is required; run initial full build first')
    for service,item in previous['images'].items():
        if service not in IMAGES:raise ValueError('Invalid service')
        result=json.loads(subprocess.check_output(['aws','ecr','batch-get-image','--region','ap-northeast-2','--repository-name',IMAGES[service],'--image-ids','imageDigest='+item['digest'],'--output','json'],text=True,encoding="utf-8"))
        if result.get('failures') or len(result.get('images',[]))!=1:raise ValueError('Previous image unavailable; rebuild is required')
    import uuid
    branch='rollback/'+sha[:12]+'-'+uuid.uuid4().hex[:8]
    git('switch','-c',branch,'origin/main')
    text=MANIFEST.read_text(encoding='utf-8')
    for service,item in previous['images'].items():text=pin(text,service,item['source'],item['digest'])
    MANIFEST.write_text(text,encoding='utf-8');previous.update(intent='rollback',rollbackFrom=sha,updatedServices=list(previous['images']))
    RELEASE.write_text(json.dumps(previous,indent=2)+'\n',encoding='utf-8')
    git('add',str(MANIFEST),str(RELEASE));git('commit','-m','Request rollback to release '+sha);git('push','-u','origin',branch)
    body=Path('.git/rollback-pr.md');body.write_text('이전 정상 이미지 digest로 복구합니다. DB·Terraform은 되돌리지 않습니다. DB 호환성을 확인하고 다른 팀원의 승인 후 병합하세요. 병합 후 deploy-check를 확인하세요.\n',encoding='utf-8')
    subprocess.run(['gh','pr','create','--base','main','--head',branch,'--title','롤백 승인 요청: '+sha[:12],'--body-file',str(body)],check=True)
if __name__=='__main__':main()
