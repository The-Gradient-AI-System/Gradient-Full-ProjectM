import { getReplyPrompts } from '../api/client';

export const REPLY_SETTINGS_CACHE_KEY = 'gradient:replySettings';

export const emptyReplySettings = () => ({
  topBlock: '',
  bottomBlock: '',
  styles: { official: '', semi_official: '' },
  prompts: { follow_up: '', recap: '', quick: '' },
});

export const readCachedReplySettings = () => {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(REPLY_SETTINGS_CACHE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

export const writeCachedReplySettings = (settings) => {
  if (typeof window === 'undefined' || !settings) return;
  try {
    window.sessionStorage.setItem(REPLY_SETTINGS_CACHE_KEY, JSON.stringify(settings));
  } catch {
    // ignore quota / private mode errors
  }
};

export const normalizeReplySettings = (data) => ({
  topBlock: data?.topBlock || '',
  bottomBlock: data?.bottomBlock || '',
  styles: {
    official: data?.styles?.official || '',
    semi_official: data?.styles?.semi_official || '',
  },
  prompts: {
    follow_up: data?.prompts?.follow_up || '',
    recap: data?.prompts?.recap || '',
    quick: data?.prompts?.quick || '',
  },
});

export const prefetchReplyPrompts = async () => {
  try {
    const data = await getReplyPrompts();
    if (data) {
      writeCachedReplySettings(normalizeReplySettings(data));
    }
  } catch {
    // prefetch is best-effort
  }
};
