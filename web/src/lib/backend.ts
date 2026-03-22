export const getBackendConfig = () => {
    const backendUrl = process.env.BACKEND_API_URL || "http://127.0.0.1:8000";
    const serviceToken = process.env.INTERNAL_SERVICE_KEY_SIGNER || "dev_service_token_123";

    return {
        backendUrl,
        serviceToken,
        headers: {
            "Content-Type": "application/json",
            "x-service-token": serviceToken,
        },
    };
};
