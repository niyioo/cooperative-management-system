import BrandSeal from './BrandSeal';
import { BRAND } from './brand';

/**
 * Seal plus optional name block.
 *   layout="stacked"    seal above the name (login, sign-up, printed documents)
 *   layout="horizontal" seal beside the name (sidebars, headers)
 *   tone="light" | "dark" matches the background the logo sits on.
 */
export default function BrandLogo({
    size = 96,
    layout = 'stacked',
    tone = 'light',
    showName = true,
    showInstitute = true,
    className = '',
}) {
    const nameColor = tone === 'dark' ? 'text-white' : 'text-[#293c9c]';
    const subColor = tone === 'dark' ? 'text-slate-400' : 'text-slate-500';
    const stacked = layout === 'stacked';

    return (
        <div
            className={`${stacked ? 'flex flex-col items-center text-center' : 'flex items-center gap-3'} ${className}`}
        >
            <BrandSeal size={size} className="shrink-0 drop-shadow-sm" />
            {showName && (
                <div className={stacked ? 'mt-4' : 'min-w-0'}>
                    <p className={`font-extrabold leading-tight tracking-tight ${nameColor} ${stacked ? 'text-2xl' : 'text-sm'}`}>
                        {BRAND.name}
                    </p>
                    {showInstitute && (
                        <p className={`${subColor} ${stacked ? 'mt-1 text-sm' : 'text-[11px] leading-snug truncate'}`}>
                            {BRAND.institute} · {BRAND.parent}
                        </p>
                    )}
                </div>
            )}
        </div>
    );
}
