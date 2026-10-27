import { register } from 'register-service-worker';

// Registers the generated Workbox worker (`sw.js`, built from
// `extendGenerateSWOptions` in quasar.config.ts). The lifecycle the app
// reacts to — "a new version is ready" — is read off `controllerchange` in
// `composables/usePwaLifecycle.ts`, so the hooks here are deliberately thin
// (finalisation 17-R16 trimmed the eight empty template stubs).
register(process.env.SERVICE_WORKER_FILE, {
  error(err) {
    console.warn('Service worker registration failed:', err);
  },
});
