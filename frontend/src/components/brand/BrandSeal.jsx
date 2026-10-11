import { useId } from 'react';
import emblem from '@/assets/emdi-emblem.svg';
import { BRAND } from './brand';

/**
 * Circular EMDI Cooperative Society seal: the EMDI emblem in the centre with
 * "EMDI COOPERATIVE" curving over the top and "SOCIETY" along the bottom.
 * Pure SVG, so it stays sharp at any size and prints cleanly.
 */
export default function BrandSeal({ size = 96, className = '', title = BRAND.name }) {
    // useId() returns values like ":r1:"; strip the colons so they are safe in url()/href references.
    const uid = useId().replace(/:/g, '');
    const topArc = `seal-top-${uid}`;
    const bottomArc = `seal-bottom-${uid}`;

    return (
        <svg
            viewBox="0 0 200 200"
            width={size}
            height={size}
            className={className}
            role="img"
            aria-label={title}
        >
            <title>{title}</title>
            <defs>
                {/* Top text sits on the arc and grows outward; bottom text hangs inward, so its baseline radius is larger. */}
                <path id={topArc} d="M 28 100 A 72 72 0 0 1 172 100" />
                <path id={bottomArc} d="M 14 100 A 86 86 0 0 0 186 100" />
            </defs>

            {/* Outer ring band */}
            <circle cx="100" cy="100" r="98" fill={BRAND.colors.navy} />
            <circle cx="100" cy="100" r="93" fill="none" stroke={BRAND.colors.white} strokeWidth="1.2" strokeOpacity="0.55" />
            {/* Inner disc */}
            <circle cx="100" cy="100" r="64" fill={BRAND.colors.white} />
            <circle cx="100" cy="100" r="64" fill="none" stroke={BRAND.colors.blue} strokeWidth="2.5" />

            <text
                fill={BRAND.colors.white}
                fontFamily="inherit"
                fontSize="17"
                fontWeight="800"
                letterSpacing="2.4"
            >
                <textPath href={`#${topArc}`} startOffset="50%" textAnchor="middle">
                    EMDI COOPERATIVE
                </textPath>
            </text>
            <text
                fill={BRAND.colors.white}
                fontFamily="inherit"
                fontSize="17"
                fontWeight="800"
                letterSpacing="4"
            >
                <textPath href={`#${bottomArc}`} startOffset="50%" textAnchor="middle">
                    SOCIETY
                </textPath>
            </text>

            {/* Separators at 9 and 3 o'clock */}
            <circle cx="21" cy="100" r="3.2" fill={BRAND.colors.white} />
            <circle cx="179" cy="100" r="3.2" fill={BRAND.colors.white} />

            {/* EMDI emblem (viewBox 40x45), centred in the inner disc */}
            <image href={emblem} x="72" y="68" width="56" height="63" />
        </svg>
    );
}
