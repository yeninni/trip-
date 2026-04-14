# trip-

전남 ECO 여행 UI를 빠르게 확인할 수 있는 정적 데모 프로젝트입니다.

## Run locally

```bash
chmod +x scripts/run_demo.sh
./scripts/run_demo.sh start
```

브라우저에서 `http://127.0.0.1:8001`로 접속하면 UI를 확인할 수 있습니다.

`8001` 포트가 이미 사용 중이면 다른 포트로 실행할 수 있습니다.

```bash
PORT=8011 ./scripts/run_demo.sh start
```

상태 확인:

```bash
./scripts/run_demo.sh status
curl -s http://127.0.0.1:8001/health
```

중지:

```bash
./scripts/run_demo.sh stop
```

## Git workflow

브랜치/커밋/푸시 운영 기준은 [docs/GIT_WORKFLOW.md](/c:/Users/jaseo/trip-/docs/GIT_WORKFLOW.md)에 정리되어 있습니다.
