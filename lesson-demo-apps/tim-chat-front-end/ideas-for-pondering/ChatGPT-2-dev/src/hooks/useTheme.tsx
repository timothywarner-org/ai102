import { useState, useEffect } from 'react';
import { getCurrentWindow } from '@tauri-apps/api/window';

export default function useTheme() {
  const [theme, setTheme] = useState<string | null>('light'); // ['light', 'dark']

  useEffect(() => {
    let unlisten: Function;
    (async () => {
      let win = getCurrentWindow();
      setTheme(await win.theme() || '');
      unlisten = await win.onThemeChanged(({ payload: newTheme }) => {
        setTheme(newTheme);
      });
    })()

    return () => {
      unlisten?.();
    };
  }, [])

  return theme;
}