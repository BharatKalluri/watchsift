export type Provider = 'netflix' | 'primevideo';

export function providerForUrl(url: string): Provider | null {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:' || parsed.port || parsed.username || parsed.password)
      return null;
    if (/^(www\.)?netflix\.com$/.test(parsed.hostname)) return 'netflix';
    if (/^(www\.)?primevideo\.com$/.test(parsed.hostname)) return 'primevideo';
  } catch {
    /* Untrusted sender or page URL. */
  }
  return null;
}

export function validProviderId(provider: Provider, id: string): boolean {
  return provider === 'netflix' ? /^\d{1,20}$/.test(id) : /^[A-Z0-9]{10,26}$/.test(id);
}
