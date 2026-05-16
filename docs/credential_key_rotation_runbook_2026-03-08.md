# 자격증명 key rotation 런북 (V3.7)

## 범위
- 대상: `user_exchange_credentials` (exchange=`UPBIT`)
- 목적: 사용자별 저장 자격증명을 신규 `key_version`으로 재암호화

## 정책
- 암호화는 `key_version`을 반드시 저장한다.
- 신규 입력/갱신은 `OPS_API_CREDENTIALS_ACTIVE_KEY_VERSION` 키를 사용한다.
- 복호화는 우선 `row.key_version`에 매핑된 키를 사용하고, 없으면 fallback 키(`OPS_API_CREDENTIALS_ENCRYPTION_KEY`)를 사용한다.
- 키링은 `OPS_API_CREDENTIALS_KEYRING_JSON`(JSON object)로 주입한다.
  - 예: `{"v1":"old-secret","v2":"new-secret"}`

## Rotation 절차
1. 배포 전 키링에 `old+new` 키를 모두 등록한다.
2. 관리자로 로그인한다.
3. `POST /api/admin/credentials/rotate`를 `dry_run=true`로 먼저 실행해 실패 건수를 확인한다.
4. 실패가 0이면 `dry_run=false`로 실제 재암호화를 수행한다.
5. 결과의 `failed_user_ids`가 있으면 해당 사용자 credential 복구를 먼저 처리한다.
6. 안정화 후 `OPS_API_CREDENTIALS_ACTIVE_KEY_VERSION`을 새 버전으로 유지한다.

## 롤백
- 즉시 롤백이 필요하면:
  1. active key version을 이전 버전으로 되돌린다.
  2. 키링에서 이전 키를 유지한 상태로 서비스 재시작한다.
- 데이터 롤백이 필요하면:
  - 동일 엔드포인트를 사용해 `target_key_version`을 이전 버전으로 지정하여 역회전한다.

## 검증
- `/api/me/credentials/upbit`에서 `is_valid=true` 확인
- scheduler 런타임에서 사용자별 credential load 성공 확인
- `POST /api/admin/credentials/rotate` 결과에서 `failed=0` 확인
