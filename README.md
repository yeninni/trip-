# trip-

전남 ECO 여행 UI를 빠르게 확인할 수 있는 정적 데모 프로젝트입니다.

## API 키 설정

API 키는 코드에 넣지 않고 환경변수로만 불러옵니다. 저장소를 클론한 뒤 아래처럼 설정하세요.

```bash
cp .env.example .env
# .env 를 열어 발급받은 키를 채웁니다
```

| 환경변수 | 용도 |
| --- | --- |
| `TOUR_API_KEY` | 한국관광공사 TourAPI (축제·혼잡도) |
| `BUS_API_KEY` | 국토교통부 버스정류소/도착정보 API |
| `LOCKER_API_KEY` | 공공데이터포털 물품보관함 API |
| `PUBLIC_DATA_API_KEY` | 위 키를 따로 두지 않을 때 공통으로 쓰는 키 |

키는 [data.go.kr](https://www.data.go.kr)에서 활용신청 후 발급받고, 일반 인증키의 **Decoding** 값을 넣습니다.
셸 환경변수로 직접 지정해도 되며(`TOUR_API_KEY=... ./scripts/run_demo.sh start`), `.env` 값보다 셸 값이 우선합니다.
키가 없으면 API는 안내 메시지와 함께 실패하고, 화면은 예시 데이터로 동작합니다.

카카오맵 JavaScript 키는 브라우저에서 쓰이는 값이라 `.env`가 아니라 `assets/config.js`로 넣습니다.

```bash
cp assets/config.example.js assets/config.js
# kakaoJsKey 값을 채웁니다
```

`assets/config.js`가 없거나 키가 비어 있으면 카카오맵 대신 Leaflet 지도로 표시됩니다.
카카오맵 키는 [developers.kakao.com](https://developers.kakao.com)에서 JavaScript 키에 허용 도메인을 등록해 보호하세요.

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

## API 엔드포인트

`server.py`가 정적 파일을 서빙하면서 아래 경로를 공공데이터 API로 프록시합니다. 브라우저에는 키가 내려가지 않습니다.

| 경로 | 프록시 대상 |
| --- | --- |
| `/api/bus/stops` | 버스정류소 좌표 조회 |
| `/api/bus/arrivals` | 정류소 도착정보 |
| `/api/tour/festivals` | TourAPI 축제 조회 |
| `/api/tour/crowd` | 관광 혼잡도 예측 |
| `/api/locker/info`, `/api/locker/detail`, `/api/locker/realtime` | 물품보관함 정보 |

## Deploy

GitHub Pages 배포용 워크플로가 들어 있습니다.

1. GitHub 저장소 `Settings > Pages` 로 이동합니다.
2. `Build and deployment` 의 `Source` 를 `GitHub Actions` 로 설정합니다.
3. `main` 브랜치에 푸시하면 자동으로 배포됩니다.

배포 주소 예시:

```text
https://yeninni.github.io/trip-/
```

GitHub Pages에는 `server.py`가 없으므로 API는 예시 데이터로 표시됩니다.
카카오맵을 배포본에서도 쓰려면 저장소 `Settings > Secrets and variables > Actions > Variables` 에
`TRIP_KAKAO_JS_KEY` 를 추가하고, `.github/workflows/deploy-pages.yml` 의 아티팩트 준비 단계 뒤에 아래 단계를 넣으세요.

```yaml
      - name: Write runtime config
        run: |
          printf 'window.TRIP_CONFIG={kakaoJsKey:"%s"};\n' "${{ vars.TRIP_KAKAO_JS_KEY }}" > dist/assets/config.js
```

## Git workflow

브랜치/커밋/푸시 운영 기준 문서는 `docs/GIT_WORKFLOW.md`를 참고하세요.
