import { useEffect } from 'react';
import GalaxyScatter from '../components/GalaxyScatter.jsx';

export default function MapPage() {
  useEffect(() => {
    const main = document.querySelector('.main');
    const body = document.body;
    const html = document.documentElement;
    const originalMainOverflow = main ? main.style.overflow : '';
    const originalBodyOverflow = body.style.overflow;
    const originalHtmlOverflow = html.style.overflow;

    if (main) main.style.overflow = 'hidden';
    body.style.overflow = 'hidden';
    html.style.overflow = 'hidden';

    return () => {
      if (main) main.style.overflow = originalMainOverflow;
      body.style.overflow = originalBodyOverflow;
      html.style.overflow = originalHtmlOverflow;
    };
  }, []);

  return (
    <div className="map-page">
      <GalaxyScatter />
    </div>
  );
}