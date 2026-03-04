# order_attempts 운영 점검 문서

이 문서는 `order_attempts` 롤아웃 이후, attempt 단위 상태가 정상적으로 유지되는지와 거래소 식별자가 재사용되지 않는지를 운영 관점에서 빠르게 점검하기 위한 체크리스트입니다.

## 1) 중복 식별자 점검

중복 `upbit_identifier` 확인:

```sql
SELECT upbit_identifier, COUNT(*) AS duplicate_count
FROM order_attempts
WHERE upbit_identifier IS NOT NULL
GROUP BY upbit_identifier
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, upbit_identifier;
```

중복 `upbit_uuid` 확인:

```sql
SELECT upbit_uuid, COUNT(*) AS duplicate_count
FROM order_attempts
WHERE upbit_uuid IS NOT NULL
GROUP BY upbit_uuid
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, upbit_uuid;
```

## 2) 최근 attempt 점검

부모 주문 상태와 함께 최근 attempt를 확인:

```sql
SELECT
    a.order_id,
    a.attempt_no,
    a.submit_reason,
    a.state AS attempt_state,
    o.state AS order_state,
    a.error_class,
    a.last_error,
    a.upbit_identifier,
    a.upbit_uuid,
    a.updated_at
FROM order_attempts a
JOIN orders o ON o.id = a.order_id
ORDER BY a.updated_at DESC
LIMIT 50;
```

## 3) 미러링된 상태 정합성 점검

최신 attempt와 `orders` 요약 상태가 다른 주문 확인:

```sql
WITH latest_attempt AS (
    SELECT order_id, MAX(attempt_no) AS attempt_no
    FROM order_attempts
    GROUP BY order_id
)
SELECT
    o.id,
    o.client_order_id,
    o.state AS order_state,
    a.state AS latest_attempt_state,
    o.error_class AS order_error_class,
    a.error_class AS latest_attempt_error_class,
    o.updated_at
FROM orders o
JOIN latest_attempt la ON la.order_id = o.id
JOIN order_attempts a
    ON a.order_id = la.order_id
   AND a.attempt_no = la.attempt_no
WHERE
    o.state <> a.state
    OR COALESCE(o.error_class, '') <> COALESCE(a.error_class, '')
ORDER BY o.updated_at DESC;
```

## 4) attempt_no 시퀀스 무결성 점검

주문별 `attempt_no`에 중복이나 누락이 있는지 확인:

```sql
SELECT
    order_id,
    COUNT(*) AS attempt_rows,
    MAX(attempt_no) AS max_attempt_no
FROM order_attempts
GROUP BY order_id
HAVING COUNT(*) <> MAX(attempt_no)
ORDER BY order_id;
```

## 5) 운영자 체크리스트

- 가장 먼저 중복 식별자 점검을 실행합니다. 결과가 한 행이라도 나오면 identifier 또는 UUID 재사용 가능성이 있으므로, REAL 운영을 계속하기 전에 검토해야 합니다.
- 배포 직후, recover 직후, 수동 cancel 이후에는 미러링된 상태 정합성 점검을 실행합니다. 결과가 나오면 `orders` 요약 상태와 최신 attempt 상태가 어긋난 것입니다.
- 마이그레이션이나 복구 이후에는 `attempt_no` 시퀀스 무결성 점검을 실행합니다. 결과가 나오면 attempt 이력의 연속성이 깨진 것이므로 merge 또는 reconcile 신뢰도가 떨어집니다.
- 최근 attempt 점검에서 같은 `order_id`에 `ERROR_NEEDS_REVIEW`가 반복되면, 재시도나 수동 취소 전에 trader 로그와 함께 원인을 확인해야 합니다.
- 어떤 쿼리든 예상 밖의 행이 반환되면, 불일치가 해소될 때까지 `TRADE_MODE`를 `SHADOW` 또는 `TEST`로 유지하는 것이 안전합니다.
