import { useEffect, useState } from 'react';
import { platform as TauriPlatform } from '@tauri-apps/plugin-os';

export default function useInfo() {
  const [platform, setPlatform] = useState('');
  const [isMac, setMac] = useState(false);

  const handleInfo = async () => {
    const p = await TauriPlatform();
    setPlatform(await TauriPlatform());
    setMac(p === 'macos');
  }

  useEffect(() => {
    handleInfo();
  }, []);

  return { platform, isMac };
}