import type {
    FinishOnboardingRequest,
    FinishOnboardingResult,
    OnboardingCatalog,
    OnboardingState,
} from 'src/models/onboarding';
import AxiosHttpClient from './axiosHttpClient';

export default class OnboardingApiService {
    private httpClient = new AxiosHttpClient();

    getStateAsync = async (): Promise<OnboardingState> =>
        await this.httpClient.get<OnboardingState>('/onboarding/state');

    completeAsync = async (): Promise<void> =>
        await this.httpClient.post<void, Record<string, never>>(
            '/onboarding/complete',
            {},
        );

    restartAsync = async (): Promise<void> =>
        await this.httpClient.post<void, Record<string, never>>(
            '/onboarding/restart',
            {},
        );

    getCatalogAsync = async (): Promise<OnboardingCatalog> =>
        await this.httpClient.get<OnboardingCatalog>('/onboarding/catalog');

    /** 14-D2 — the wizard's whole draft (preferences, household settings,
     *  catalogue seed, starter items, demo dataset) in one transaction, which
     *  also stamps completion. All of it lands or none of it does. */
    finishAsync = async (request: FinishOnboardingRequest): Promise<FinishOnboardingResult> =>
        await this.httpClient.post<FinishOnboardingResult, FinishOnboardingRequest>(
            '/onboarding/finish',
            request,
        );
}
