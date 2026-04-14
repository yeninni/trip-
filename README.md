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

## Deploy

GitHub Pages 배포용 워크플로가 들어 있습니다.

1. GitHub 저장소 `Settings > Pages` 로 이동합니다.
2. `Build and deployment` 의 `Source` 를 `GitHub Actions` 로 설정합니다.
3. `ui` 브랜치에 푸시하면 자동으로 배포됩니다.

배포 주소 예시:

```text
https://yeninni.github.io/trip-/
```
