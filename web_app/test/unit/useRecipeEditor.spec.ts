// @vitest-environment jsdom
// buildUpdateCommand — the recipe PATCH body. Pins the step-image contract:
// `step_images[]` is a full replace, so a saved image must ride along (as its
// image id) or the server drops it.
import { describe, expect, it } from 'vitest';

import { buildUpdateCommand, emptyRecipeForm } from 'src/composables/useRecipeEditor';
import type { Recipe } from 'src/models/recipe';

const src = { ...emptyRecipeForm(), recipe_id: 'r1' } as unknown as Recipe;

describe('buildUpdateCommand step_images', () => {
    it('sends saved images by id and new uploads by data URL, in order', () => {
        const form = emptyRecipeForm();
        form.step_images = [
            { client_id: 'saved-1', existing_image_id: 'saved-1', preview_url: '/x', data_url: '' },
            { client_id: 'new-1', existing_image_id: null, preview_url: 'data:image/jpeg;base64,AAA', data_url: 'data:image/jpeg;base64,AAA' },
        ];
        const cmd = buildUpdateCommand(form, src, { image: false, stepImages: true });
        expect(cmd.step_images).toEqual(['saved-1', 'data:image/jpeg;base64,AAA']);
    });

    it('omits step_images when they were not touched', () => {
        const cmd = buildUpdateCommand(emptyRecipeForm(), src, { image: false, stepImages: false });
        expect(cmd.step_images).toBeUndefined();
    });
});
