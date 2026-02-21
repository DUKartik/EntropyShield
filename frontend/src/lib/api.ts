
export const API_BASE_URL = '/api';

export interface APIError {
    message: string;
    status?: number;
}

async function handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
        let errorMessage = `HTTP error! status: ${response.status}`;
        try {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorData.message || errorMessage;
        } catch (e) {
            const text = await response.text();
            if (text) errorMessage = text;
        }
        throw { message: errorMessage, status: response.status } as APIError;
    }
    return response.json();
}

export const api = {
    get: async <T>(endpoint: string): Promise<T> => {
        const response = await fetch(`${API_BASE_URL}${endpoint}`);
        return handleResponse<T>(response);
    },

    post: async <T>(endpoint: string, data: any, isFormData = false): Promise<T> => {
        const headers: HeadersInit = isFormData ? {} : { 'Content-Type': 'application/json' };
        const body = isFormData ? data : JSON.stringify(data);

        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'POST',
            headers,
            body,
        });
        return handleResponse<T>(response);
    },

    delete: async <T>(endpoint: string): Promise<T> => {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'DELETE',
        });
        return handleResponse<T>(response);
    }
};
