/** A temporary id for a row the server hasn't saved yet (an ingredient,
 *  step, section or image in an editor), so rows can point at each other
 *  before real ids exist. */
export function newClientId(): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID();
    }
    return `c${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}
