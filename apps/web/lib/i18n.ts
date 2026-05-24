export type LocaleCode = "en" | "ko";

export type DashboardText = {
  language: string;
  korean: string;
  english: string;
  title: string;
  subtitle: string;
  serverTime: string;
  polling: string;
  refresh: string;
  enable: string;
  killSwitch: string;
  confirmEnable: string;
  confirmDisable: string;
  mode: string;
  bot: string;
  lastTick: string;
  haltReason: string;
  alertTitle: string;
  noHaltMessage: string;
  todayPnl: string;
  basis: string;
  lossUsage: string;
  ofDailyLimit: string;
  start: string;
  last: string;
  realized: string;
  unrealized: string;
  triggered: string;
  threshold: string;
  currentPnl: string;
  ordersRisk: string;
  needsReviewTop: string;
  updated: string;
  market: string;
  side: string;
  intent: string;
  error: string;
  noRows: string;
  executionQuality: string;
  avgSlippage: string;
  p95Slippage: string;
  avgFillTime: string;
  avgPartialFills: string;
  breach24h: string;
  executed: string;
  slipPct: string;
  fillMs: string;
  configSummary: string;
  timeframe: string;
  markets: string;
  dailyLossLimit: string;
  targetExposure: string;
  maxTotalExposure: string;
  maxPerMarket: string;
  minRebalance: string;
  minOrderBuffer: string;
  fillTimeouts: string;
  reprice: string;
  slippageBudget: string;
  notifyInterval: string;
  updatedAt: string;
  viewPnl: string;
  viewOrders: string;
  viewExecution: string;
  viewControl: string;
  statusRunning: string;
  statusHalted: string;
  statusDisabled: string;
  statusDegraded: string;
  haltDailyLoss: string;
  haltSlippage: string;
  sideBid: string;
  sideAsk: string;
  entry: string;
  exit: string;
  rebalance: string;
};

export const DASHBOARD_TEXT: Record<LocaleCode, DashboardText> = {
  en: {
    language: "Language",
    korean: "Korean",
    english: "English",
    title: "Don't worry, Be happy",
    subtitle: "Quant Trading",
    serverTime: "Server time",
    polling: "Polling",
    refresh: "Refresh",
    enable: "Enable",
    killSwitch: "Kill Switch",
    confirmEnable: "Enable bot now?",
    confirmDisable: "Disable bot now?",
    mode: "Mode",
    bot: "Bot",
    lastTick: "Last Tick",
    haltReason: "Halt Reason",
    alertTitle: "ALERT: Scheduler HALT",
    noHaltMessage: "No active halt reason.",
    todayPnl: "Today PnL",
    basis: "Basis",
    lossUsage: "loss usage",
    ofDailyLimit: "of daily limit",
    start: "Start",
    last: "Last",
    realized: "Realized",
    unrealized: "Unrealized",
    triggered: "Triggered",
    threshold: "Threshold",
    currentPnl: "Current PnL",
    ordersRisk: "Orders / Risk Snapshot",
    needsReviewTop: "Needs Review (Top 10)",
    updated: "Updated",
    market: "Market",
    side: "Side",
    intent: "Intent",
    error: "Error",
    noRows: "No rows",
    executionQuality: "Execution Quality",
    avgSlippage: "Avg Slippage",
    p95Slippage: "P95 Slippage",
    avgFillTime: "Avg Fill Time",
    avgPartialFills: "Avg Partial Fills",
    breach24h: "24h Breach",
    executed: "Executed",
    slipPct: "Slip %",
    fillMs: "Fill ms",
    configSummary: "Config Summary",
    timeframe: "Timeframe",
    markets: "Markets",
    dailyLossLimit: "Daily Loss Limit",
    targetExposure: "Target Exposure",
    maxTotalExposure: "Max Total Exposure",
    maxPerMarket: "Max Per Market",
    minRebalance: "Min Rebalance",
    minOrderBuffer: "Min Order Buffer",
    fillTimeouts: "Fill Timeouts",
    reprice: "Reprice",
    slippageBudget: "Slippage Budget",
    notifyInterval: "Notify Interval",
    updatedAt: "Updated At",
    viewPnl: "Open PnL",
    viewOrders: "Open Orders",
    viewExecution: "Open Execution",
    viewControl: "Open Bot Control",
    statusRunning: "RUNNING",
    statusHalted: "HALTED",
    statusDisabled: "DISABLED",
    statusDegraded: "DEGRADED",
    haltDailyLoss: "Daily loss limit",
    haltSlippage: "Slippage budget breach",
    sideBid: "Buy",
    sideAsk: "Sell",
    entry: "Entry",
    exit: "Exit",
    rebalance: "Rebalance"
  },
  ko: {
    language: "언어",
    korean: "한국어",
    english: "영어",
    title: "Don't worry, Be happy",
    subtitle: "퀀트 트레이딩",
    serverTime: "서버 시각",
    polling: "폴링",
    refresh: "새로고침",
    enable: "활성화",
    killSwitch: "킬 스위치",
    confirmEnable: "봇을 지금 활성화할까요?",
    confirmDisable: "봇을 지금 비활성화할까요?",
    mode: "모드",
    bot: "봇 상태",
    lastTick: "마지막 틱",
    haltReason: "중지 사유",
    alertTitle: "경고: 스케줄러 중지",
    noHaltMessage: "활성 중지 사유가 없습니다.",
    todayPnl: "오늘 손익",
    basis: "기준",
    lossUsage: "손실 사용률",
    ofDailyLimit: "일일 한도 대비",
    start: "시작 자산",
    last: "현재 자산",
    realized: "실현 손익",
    unrealized: "미실현 손익",
    triggered: "발생 시각",
    threshold: "임계값",
    currentPnl: "현재 손익",
    ordersRisk: "주문 / 리스크 요약",
    needsReviewTop: "검토 필요 주문 (상위 10건)",
    updated: "업데이트",
    market: "마켓",
    side: "방향",
    intent: "의도",
    error: "오류",
    noRows: "데이터 없음",
    executionQuality: "체결 품질",
    avgSlippage: "평균 슬리피지",
    p95Slippage: "P95 슬리피지",
    avgFillTime: "평균 체결 시간",
    avgPartialFills: "평균 부분 체결",
    breach24h: "24시간 초과",
    executed: "체결 시각",
    slipPct: "슬리피지 %",
    fillMs: "체결 ms",
    configSummary: "설정 요약",
    timeframe: "타임프레임",
    markets: "마켓",
    dailyLossLimit: "일일 손실 한도",
    targetExposure: "목표 노출",
    maxTotalExposure: "최대 총 노출",
    maxPerMarket: "마켓별 최대 노출",
    minRebalance: "최소 리밸런스",
    minOrderBuffer: "최소 주문 버퍼",
    fillTimeouts: "체결 대기 시간",
    reprice: "재호가",
    slippageBudget: "슬리피지 예산",
    notifyInterval: "알림 주기",
    updatedAt: "업데이트 시각",
    viewPnl: "손익 열기",
    viewOrders: "주문 열기",
    viewExecution: "체결 지표 열기",
    viewControl: "봇 제어 열기",
    statusRunning: "실행 중",
    statusHalted: "중지됨",
    statusDisabled: "비활성화",
    statusDegraded: "성능 저하",
    haltDailyLoss: "일일 손실 한도 초과",
    haltSlippage: "슬리피지 예산 초과",
    sideBid: "매수",
    sideAsk: "매도",
    entry: "진입",
    exit: "청산",
    rebalance: "리밸런스"
  }
};
