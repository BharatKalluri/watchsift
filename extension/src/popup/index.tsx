import './popup.css';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { DEFAULTS, type Settings, validSettings } from '../shared/types';

type ToggleKey = 'enabled' | 'filtering';

function Toggle({
  id,
  title,
  children,
  checked,
  onChange,
}: {
  id: ToggleKey;
  title: string;
  children?: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <>
      <div className="flex items-start justify-between gap-4">
        <div>
          <label htmlFor={id}>{title}</label>
          {children && <p>{children}</p>}
        </div>
        <input
          id={id}
          type="checkbox"
          role="switch"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          className="relative m-0 h-5 w-[34px] shrink-0 cursor-pointer appearance-none rounded-full bg-track checked:bg-gold hover:outline hover:outline-soft hover:outline-offset-2 after:absolute after:top-[3px] after:left-[3px] after:size-[14px] after:rounded-full after:bg-ink after:content-[''] checked:after:left-[17px] motion-safe:after:transition-[left] motion-safe:after:duration-120"
        />
      </div>
    </>
  );
}

function Popup() {
  const [settings, setSettings] = useState(DEFAULTS);
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const savePending = useRef(false);
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState('Checking connection…');

  useEffect(() => {
    let active = true;
    async function refreshStatus() {
      const state = await chrome.runtime.sendMessage({ action: 'status' });
      if (active) {
        setStatus(state?.status || 'Open Netflix or Prime Video to start');
      }
    }
    async function init() {
      const stored = await chrome.storage.local.get('settings');
      const candidate = { ...DEFAULTS, ...((stored.settings as Partial<Settings>) || {}) };
      if (!active) return;
      if (validSettings(candidate)) setSettings(candidate);
      setReady(true);
      await refreshStatus();
    }
    const onChanged = (changes: Record<string, chrome.storage.StorageChange>, area: string) => {
      if (area === 'local' && (changes.engine || changes.settings))
        void refreshStatus().catch(() => {});
    };
    chrome.storage.onChanged.addListener(onChanged);
    void init().catch(() => {
      if (active) setStatus('Could not load settings. Reload the extension and try again.');
    });
    return () => {
      active = false;
      chrome.storage.onChanged.removeListener(onChanged);
    };
  }, []);

  async function save(next: Settings) {
    if (savePending.current || !validSettings(next)) return;
    const previous = settings;
    savePending.current = true;
    setSettings(next);
    setSaving(true);
    setMessage('Saving…');
    try {
      const response = await chrome.runtime.sendMessage({ action: 'settings', settings: next });
      if (response?.saved !== true) throw new Error('Settings were not saved');
      setMessage('Saved');
    } catch {
      setSettings(previous);
      setMessage('Could not save. Reload the extension and try again.');
    } finally {
      savePending.current = false;
      setSaving(false);
    }
  }

  const toggle = (id: ToggleKey, title: string, children?: ReactNode) => (
    <Toggle
      id={id}
      title={title}
      checked={settings[id]}
      onChange={(checked) => void save({ ...settings, [id]: checked })}
    >
      {children}
    </Toggle>
  );

  return (
    <>
      <header className="flex items-center justify-between border-b border-line px-[22px] pt-[22px] pb-[18px]">
        <div className="flex items-center gap-[9px]">
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="size-[25px] fill-none stroke-gold stroke-[1.8] [stroke-linejoin:round]"
          >
            <path d="M4 5h16L14 12v6l-4 2v-8Z" />
          </svg>
          <h1 className="font-serif text-[25px] font-medium tracking-[-0.025em]">WatchSift</h1>
        </div>
        <span className="text-[12px] text-soft">Netflix &amp; Prime Video</span>
      </header>
      <main className="p-[22px]">
        <fieldset disabled={!ready || saving} className="m-0 min-w-0 border-0 p-0">
          {toggle('enabled', 'Show IMDb ratings', 'A little more context for your next watch.')}
          <section
            aria-labelledby="filter-title"
            className="mt-[25px] border-t border-line pt-[22px]"
          >
            <h2 id="filter-title" className="sr-only">
              Rating filters
            </h2>
            {toggle('filtering', 'Dim below my minimums')}
            <form
              id="thresholds"
              onSubmit={(event) => {
                event.preventDefault();
                const form = event.currentTarget;
                void save({
                  ...settings,
                  minRating: (form.elements.namedItem('minRating') as HTMLInputElement)
                    .valueAsNumber,
                  minVotes: (form.elements.namedItem('minVotes') as HTMLInputElement).valueAsNumber,
                });
              }}
            >
              <div className="mt-[21px] grid grid-cols-[1fr_30px_1.35fr] items-center gap-2">
                {(['minRating', 'minVotes'] as const).map((id, index) => (
                  <div key={id} className="contents">
                    {index === 1 && <span className="text-center text-[10px] text-gold">AND</span>}
                    <label htmlFor={id} className="text-[12px] text-soft">
                      {id === 'minRating' ? 'IMDb rating' : 'Rating votes'}
                      <input
                        key={settings[id]}
                        id={id}
                        name={id}
                        type="number"
                        min="0"
                        max={id === 'minRating' ? 10 : 1000000000}
                        step={id === 'minRating' ? 0.1 : 1}
                        required
                        defaultValue={settings[id]}
                        className="mt-2 block w-full rounded-md border border-track bg-panel px-[10px] py-[9px] text-[23px] text-paper tabular-nums caret-gold"
                      />
                      <span className="mt-[6px] block text-[10px] font-normal text-muted">
                        {id === 'minRating' ? 'out of 10' : 'people who rated it'}
                      </span>
                    </label>
                  </div>
                ))}
              </div>
              <button
                type="submit"
                id="save"
                className="mt-[18px] w-full cursor-pointer rounded-md bg-gold px-3 py-[10px] font-semibold text-ink hover:bg-[#ffdf87] active:bg-[#d6b143] disabled:cursor-wait disabled:bg-track"
              >
                Save minimums
              </button>
            </form>
            <p className="mt-[10px] text-[11px]">
              Titles need to meet both. Missing or uncertain ratings stay visible.
            </p>
          </section>
          <p
            id="status"
            role="status"
            className="mt-[22px] border-t border-line pt-[17px] text-[11px]"
          >
            {status}
          </p>
        </fieldset>
        <p id="message" aria-live="polite" className="min-h-[18px] text-[11px] text-gold">
          {message}
        </p>
      </main>
      <footer className="flex justify-between gap-3 border-t border-line px-[22px] py-[14px] text-[10px] text-muted">
        <a href="privacy.html" target="_blank" rel="noopener">
          Privacy &amp; data
        </a>
        <a href="https://www.imdb.com/" target="_blank" rel="noopener">
          Data courtesy of IMDb
        </a>
      </footer>
    </>
  );
}

createRoot(document.getElementById('root')!).render(<Popup />);
