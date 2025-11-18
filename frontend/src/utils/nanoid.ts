export function nanoid(size = 10): string {
  const chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz-';
  let id = '';
  const cryptoObj: Crypto | undefined = (globalThis as any).crypto;
  if (cryptoObj && 'getRandomValues' in cryptoObj) {
    const arr = new Uint8Array(size);
    cryptoObj.getRandomValues(arr);
    for (let i = 0; i < size; i++) id += chars[arr[i] % chars.length];
    return id;
  }
  for (let i = 0; i < size; i++) id += chars[Math.floor(Math.random() * chars.length)];
  return id;
}

export default nanoid;
