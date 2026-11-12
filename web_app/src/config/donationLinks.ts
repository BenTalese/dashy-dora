// R-003 single source for the project's "support the project" link. A static
// AUTHOR channel baked into the open-source build, like the support channel
// (`support_channel.py`): the author's, not per-install admin config, so it
// lives as a committed constant, not an AppSetting. Every consumer reads from
// here: the three <DonateButton> placements (menu bar, auth shell, settings)
// and the About page. `.github/FUNDING.yml`, the README donate section and the
// issue chooser carry the same link by hand.
//
// PayPal only: GitHub Sponsors just routed through to PayPal anyway, so a
// second option was a menu with nothing to choose between.
export const DONATION_URL =
    'https://www.paypal.com/donate/?business=BBEWWLKS6MY2G&no_recurring=1&currency_code=AUD';
