let _configFaultCount = 0;

export function setConfigFault(count: number): void {
  _configFaultCount = count;
}

export function resetConfigFault(): void {
  _configFaultCount = 0;
}

export function consumeConfigFault(): boolean {
  if (process.env.VERUM_TEST_MODE !== "1") return false;
  if (_configFaultCount <= 0) return false;
  _configFaultCount--;
  return true;
}
