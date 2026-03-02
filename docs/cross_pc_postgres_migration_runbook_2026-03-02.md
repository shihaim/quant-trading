# PC 간 PostgreSQL 마이그레이션 런북

- 작성일: 2026-03-02
- 대상: 개발 담당자 / 인프라 운영 담당자
- 범위: Docker 기반 PostgreSQL을 사용하는 소스 PC에서 타깃 PC로 `quant-trading` 데이터를 SSH 터널 기반으로 이관하는 절차

## 1. 목적

이 문서는 `quant-trading` 데이터베이스를 한 PC에서 다른 PC로 옮길 때,
동일한 절차를 반복 수행할 수 있도록 정리한 운영 런북이다.

이번 문서의 기준 경로는 다음과 같다.

- 마이그레이션 스크립트는 소스 PC에서 실행
- 타깃 PostgreSQL 포트는 외부에 직접 노출하지 않음
- SSH 키 기반 포트 포워딩(터널) 사용
- 저장소 내 SQLAlchemy 마이그레이션 CLI 사용: `python -m trader.app.migrate_db`

다음과 같은 상황에서 이 경로를 우선 권장한다.

- 소스/타깃 PC가 같은 내부망(LAN)에 있음
- 타깃 PostgreSQL이 `127.0.0.1`에만 바인딩된 상태를 유지해야 함
- 타깃 환경이 향후 계속 사용할 운영 환경이 됨

## 2. 적용 환경

2026-03-02 실제 성공 사례 기준 환경:

- 소스 PC: `192.168.0.7`
- 타깃 PC: `192.168.0.6`
- 소스 PostgreSQL: Docker 컨테이너 `qt-postgres`, 로컬 노출 포트 `127.0.0.1:15432`
- 타깃 PostgreSQL: Docker 컨테이너 `qt-postgres`, 타깃 PC 내부에서만 `127.0.0.1:15432`
- 소스 PC에서 사용할 SSH 터널 로컬 포트: `127.0.0.1:25432`

두 PC가 같은 공인 IP를 공유하더라도 문제 없다. 실제 연결은 공인 IP가 아니라
사설 IP(`192.168.0.x`) 기준으로 진행한다.

## 3. 어떤 데이터가 이동하는가

기본 마이그레이션 대상 테이블:

- `bot_config`
- `timeframe_config`
- `orders`
- `fills`
- `trade_metrics`
- `candles`

`--copy-snapshot-tables` 옵션을 추가하면 아래 현재 상태 테이블도 함께 동기화한다.

- `positions`
- `paper_wallet`
- `daily_equity`

주의사항:

- `bot_config`는 기본적으로 `target_wins` 정책이다. 즉 타깃 값이 유지되고, 소스 값으로 덮지 않는다.
- `paper_wallet`은 소스에 행이 있을 때만 복사된다. 소스가 비어 있으면 타깃 값을 유지한다.
- 스키마 문서 테이블과 자동 생성 view는 수동 복사 대상이 아니다. 앱 bootstrap 로직이 생성한다.

## 4. 사전 준비

### 4.1 소스 PC 준비사항

- 저장소가 소스 PC에 존재해야 한다.
- Python 실행 환경이 준비되어 있어야 한다.
- `postgresql+psycopg://...` URL을 사용하므로 `psycopg` 드라이버가 설치되어 있어야 한다.

최소 드라이버 설치:

```powershell
python -m pip install "psycopg[binary]>=3.2.0"
```

권장 전체 개발 환경:

```powershell
python -m pip install -e .[dev]
```

### 4.2 타깃 PC 준비사항

- OpenSSH Server가 활성화되어 있어야 한다.
- SSH 키 인증이 정상 동작해야 한다.
- 타깃 PostgreSQL은 계속 로컬 바인딩(`127.0.0.1`) 상태를 유지해도 된다.

### 4.3 Docker / DB 준비사항

- 소스 PostgreSQL 컨테이너가 실행 중이어야 한다.
- 타깃 PostgreSQL 컨테이너가 실행 중이어야 한다.
- 소스/타깃 DB 계정 정보가 준비되어 있어야 한다.

소스 컨테이너 상태 확인:

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

소스 `qt-postgres`가 꺼져 있으면:

```powershell
docker compose up -d postgres
```

## 5. SSH 터널 구성

소스 PC에서 아래 명령으로 SSH 터널을 열고, 이 창은 작업이 끝날 때까지 유지한다.

```powershell
ssh -i $env:USERPROFILE\.ssh\qt_migration_key -N -L 25432:127.0.0.1:15432 hsw@192.168.0.6
```

의미:

- 소스 PC의 `127.0.0.1:25432`
- 타깃 PC의 `127.0.0.1:15432`로 포워딩
- 결과적으로 타깃 Docker PostgreSQL에 접속

다른 소스 PC 터미널에서 터널 상태 확인:

```powershell
Test-NetConnection 127.0.0.1 -Port 25432
```

기대 결과:

- `TcpTestSucceeded : True`

## 6. 마이그레이션 전 점검

마이그레이션 전에 쓰기 트래픽을 중지한다.

권장:

- `qt-trader` 중지
- `qt-ops-api` 중지

이유:

- 이관 중 데이터가 바뀌면 row count와 상태 스냅샷이 어긋날 수 있다.

소스 PostgreSQL 로컬 포트 확인:

```powershell
Test-NetConnection 127.0.0.1 -Port 15432
```

기대 결과:

- `TcpTestSucceeded : True`

## 7. 드라이런(dry-run)

실제 반영 전에 반드시 드라이런을 먼저 수행한다.

실제 성공했던 명령 예시:

```powershell
python -m trader.app.migrate_db `
  --source-url "postgresql+psycopg://trader:<SOURCE_PASSWORD>@127.0.0.1:15432/trading" `
  --target-url "postgresql+psycopg://trader:<TARGET_PASSWORD>@127.0.0.1:25432/trading" `
  --copy-snapshot-tables `
  --dry-run `
  --verbose
```

확인할 항목:

- `migration_summary mode=projected`
- 전체 `inserted`, `updated`, `skipped`
- 테이블별 반영 예상 수치
- `warning=` 로그 존재 여부

2026-03-02 기준 실제 드라이런 결과:

- 전체 예상: `inserted=158`, `updated=8`, `skipped=1`
- `bot_config`: 타깃 유지로 1건 skip
- `timeframe_config`: 8건 update
- `orders`: 2건 insert
- `fills`: 1건 insert
- `trade_metrics`: 1건 insert
- `candles`: 151건 insert
- `positions`: 1건 insert
- `paper_wallet`: 소스 행이 없어 변경 없음
- `daily_equity`: 2건 insert

다음과 같은 경우 실제 실행으로 넘어가지 말고 중단한다.

- 예상치 못한 conflict warning이 발생함
- insert/update 수치가 기대와 크게 다름
- source/target 연결이 불안정함

## 8. 실제 마이그레이션

드라이런 결과가 정상이라면 동일 옵션에서 `--dry-run`만 제거하고 실제 반영한다.

```powershell
python -m trader.app.migrate_db `
  --source-url "postgresql+psycopg://trader:<SOURCE_PASSWORD>@127.0.0.1:15432/trading" `
  --target-url "postgresql+psycopg://trader:<TARGET_PASSWORD>@127.0.0.1:25432/trading" `
  --copy-snapshot-tables `
  --verbose
```

2026-03-02 실제 반영 결과:

- 전체 적용: `inserted=158`, `updated=8`, `skipped=1`
- 테이블별 수치는 드라이런과 동일

## 9. 마이그레이션 후 검증

타깃 DB row count를 확인해 실제 반영 상태를 검증한다.

소스 PC에서 SSH 터널을 유지한 상태로 Python 검증 예시:

```powershell
@'
import psycopg

conn = psycopg.connect("postgresql://trader:<TARGET_PASSWORD>@127.0.0.1:25432/trading")
with conn, conn.cursor() as cur:
    for table in ["orders", "fills", "trade_metrics", "candles", "positions", "daily_equity", "paper_wallet"]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"{table}:{cur.fetchone()[0]}")
'@ | python -
```

2026-03-02 실제 확인값:

- `orders: 2`
- `fills: 1`
- `trade_metrics: 1`
- `candles: 151`
- `positions: 1`
- `daily_equity: 2`
- `paper_wallet: 1`

추가로 확인할 항목:

- 타깃 애플리케이션의 `DATABASE_URL`이 타깃 PostgreSQL을 가리키는지
- 타깃 `qt-trader`, `qt-ops-api`가 정상 기동하는지
- 대시보드 / API에서 기대한 데이터가 보이는지

## 10. 자주 발생하는 장애

### 10.1 `ModuleNotFoundError: No module named 'psycopg'`

원인:

- 현재 Python 환경에 PostgreSQL 드라이버가 없음

조치:

```powershell
python -m pip install "psycopg[binary]>=3.2.0"
```

### 10.2 SSH 터널 포트는 열렸는데 마이그레이션이 멈춤

2026-03-02 실제 원인:

- 타깃 터널 포트 `25432`는 열려 있었음
- 소스 로컬 PostgreSQL 포트 `15432`는 닫혀 있었음
- 소스 `qt-postgres`가 실행 중이 아니었음

조치:

```powershell
docker compose up -d postgres
Test-NetConnection 127.0.0.1 -Port 15432
```

### 10.3 `-i`로 키를 줬는데도 비밀번호를 물어봄

가능한 원인:

- 공개키가 올바르게 등록되지 않음
- SSH 로그인 계정명이 틀림
- 잘못된 `authorized_keys` 경로에 키를 넣음
- 관리자 계정의 경우 `C:\ProgramData\ssh\administrators_authorized_keys`를 사용할 수 있음

확인 항목:

- `whoami`, `$env:USERNAME`으로 실제 계정명 확인
- `PubkeyAuthentication yes` 확인
- 실제 `AuthorizedKeysFile` 경로 확인
- 설정 변경 후 `sshd` 재시작

### 10.4 드라이런에서 conflict warning이 발생함

마이그레이션 로직은 다음 경우 조용한 데이터 손상을 막기 위해 경고 또는 예외를 발생시킨다.

- `orders`: 같은 `client_order_id`인데 정체성 필드가 다름
- `fills`: 같은 `trade_id`인데 payload가 다름
- `trade_metrics`: 타깃 row가 더 최신인데 값이 다름

조치:

- 실제 실행 전에 해당 레코드를 source/target 양쪽에서 직접 조회
- 원인 확인 전에는 live run 진행 금지

## 11. 보안 메모

- PostgreSQL 포트를 직접 LAN에 노출하는 방식보다 SSH 터널을 우선 사용한다.
- 비밀번호를 평문으로 오래 보관하거나 쉘 히스토리에 남기지 않도록 주의한다.
- 이관 과정에서 자격 증명이 공유되었다면 필요 시 교체한다.
- SSH 터널은 마이그레이션 및 검증이 끝나면 즉시 종료한다.

## 12. 반복 실행 체크리스트

다음번 동일 작업 시 아래 순서를 그대로 따른다.

1. 소스/타깃 `qt-postgres` 컨테이너가 healthy인지 확인
2. 현재 Python 환경에 `psycopg`가 설치되어 있는지 확인
3. SSH 키 인증으로 타깃 PC 접속이 가능한지 확인
4. 소스 PC에서 SSH 터널 오픈
5. 소스 PC에서 `127.0.0.1:15432`, `127.0.0.1:25432` 연결 확인
6. 소스 측 쓰기 트래픽(`qt-trader`, `qt-ops-api`) 중지
7. `--dry-run --copy-snapshot-tables --verbose` 실행
8. 예상 반영 수치와 warning 점검
9. 동일 옵션으로 live run 실행
10. 타깃 row count 및 앱 기동 확인
11. SSH 터널 종료

## 13. 명령 템플릿

### 드라이런

```powershell
python -m trader.app.migrate_db `
  --source-url "postgresql+psycopg://trader:<SOURCE_PASSWORD>@127.0.0.1:15432/trading" `
  --target-url "postgresql+psycopg://trader:<TARGET_PASSWORD>@127.0.0.1:25432/trading" `
  --copy-snapshot-tables `
  --dry-run `
  --verbose
```

### 실제 반영

```powershell
python -m trader.app.migrate_db `
  --source-url "postgresql+psycopg://trader:<SOURCE_PASSWORD>@127.0.0.1:15432/trading" `
  --target-url "postgresql+psycopg://trader:<TARGET_PASSWORD>@127.0.0.1:25432/trading" `
  --copy-snapshot-tables `
  --verbose
```
