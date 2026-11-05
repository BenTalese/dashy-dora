import { ICONS } from 'src/style/icons';

// R-003 single source for the project's donation / "support the project"
// links. These are static AUTHOR channels baked into the open-source build,
// like the support channel (`support_channel.py`): they're the author's, not
// per-install admin config, so they live as a committed constant, not an
// AppSetting. Every consumer reads from here: the three <DonateButton>
// placements (menu bar, auth shell, settings) and the About page.
// `.github/FUNDING.yml`, the README donate section and the issue chooser
// carry the same links by hand.

export interface DonationPlatform {
    /** Display label shown in the popover row. */
    label: string;
    /** External URL, opens in a new tab. */
    url: string;
    /** Row icon (from the central ICONS catalogue). */
    icon: string;
    /** The single platform the buttons headline as the primary CTA. */
    primary?: boolean;
}

// PayPal for one-off gifts, GitHub Sponsors for recurring support from the
// GitHub audience. Deliberately no more: one-off and recurring are covered.
export const DONATION_PLATFORMS: DonationPlatform[] = [
    {
        label: 'PayPal',
        url: 'https://www.paypal.com/donate/?business=BBEWWLKS6MY2G&no_recurring=1&currency_code=AUD',
        icon: ICONS.volunteer_activism,
        primary: true,
    },
    {
        label: 'GitHub Sponsors',
        url: 'https://github.com/sponsors/BenTalese',
        icon: ICONS.favorite,
    },
];

/** The headline platform the buttons default to (first `primary`, else first). */
export const PRIMARY_DONATION: DonationPlatform =
    DONATION_PLATFORMS.find((p) => p.primary) ?? DONATION_PLATFORMS[0]!;
