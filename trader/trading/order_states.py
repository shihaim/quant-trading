# 업비트 주문 상태를 내부 상태로 정규화하기 위한 매핑 테이블.
UPBIT_TO_LOCAL = {
    "wait": "OPEN",
    "watch": "OPEN",
    "done": "FILLED",
    "cancel": "CANCELED",
}

# 로컬에서 "아직 닫히지 않은 주문"으로 간주하는 상태 집합.
LOCAL_OPEN_STATES = {"NEW", "SENT", "OPEN", "PARTIAL", "WAIT"}
