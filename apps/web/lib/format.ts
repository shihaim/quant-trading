type IntlLocale = "en-US" | "ko-KR";

export function asPct(value: number | null | undefined, locale: IntlLocale = "en-US"): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  const formatted = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3
  }).format(value * 100);
  return `${formatted}%`;
}

export function asKrw(value: number | null | undefined, locale: IntlLocale = "en-US"): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  const suffix = locale === "ko-KR" ? "원" : "KRW";
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(value)} ${suffix}`;
}

export function asTime(value: string | null | undefined, locale: IntlLocale = "en-US"): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return `${date.toLocaleDateString(locale)} ${date.toLocaleTimeString(locale)}`;
}

export function asInt(value: number | null | undefined, locale: IntlLocale = "en-US"): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value);
}

export function asDecimal(
  value: number | null | undefined,
  locale: IntlLocale = "en-US",
  fractionDigits = 2
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 0,
    maximumFractionDigits: fractionDigits
  }).format(value);
}

export function short(value: string | null | undefined, max = 42): string {
  if (!value) {
    return "-";
  }
  if (value.length <= max) {
    return value;
  }
  return `${value.slice(0, max - 3)}...`;
}
