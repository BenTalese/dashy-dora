// PROPOSAL_RECIPE_IMAGE_STEPS — shared types for the image-mode step
// editor. Extracted from RecipeStepImagesEditor.vue so the host page can
// import the row type from a plain .ts module (mirrors recipeStepEditorTypes
// — cleaner than importing a type out of an SFC's <script setup>).

/** The empty-state copy, shared by the viewer and the editor so the block
 *  says the same thing whichever face you're on (owner 2026-09-03; R-003). */
export const NO_STEP_IMAGES_COPY =
    'No images yet. Add photos of your steps in the order you want to cook them. '
    + 'Cook mode will show them as a scrollable gallery.';

export type EditableStepImage = {
    /** Unique key for vuedraggable + row tracking. crypto.randomUUID() for
     *  freshly-uploaded rows; the existing RecipeStepImage.image_id when
     *  hydrated from the server. */
    client_id: string;
    /** Non-null when this row was loaded from a saved RecipeStepImage; the
     *  bytes endpoint URL works without needing data_url. Null for rows
     *  added in this edit session (data_url carries the payload). */
    existing_image_id: string | null;
    /** What the editor renders — a data URL for freshly-picked rows, or
     *  the `/recipes/<id>/step-images/<image_id>` URL for hydrated rows. */
    preview_url: string;
    /** The `data:image/jpeg;base64,...` payload to POST on save. Empty
     *  string for hydrated rows — they round-trip by sending their
     *  existing_image_id in the same `step_images[]` slot, so the server
     *  keeps the saved image in the new order. */
    data_url: string;
};
