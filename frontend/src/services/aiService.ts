import { API_BASE_URL } from '../config';

export const generateExercise = async (prompt: string, language: string = 'python') => {
    const token = localStorage.getItem('token');
    const headers: HeadersInit = {
        'Content-Type': 'application/json',
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}/ai/generate/exercise`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ prompt, language }),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to generate exercise');
    }

    return response.json();
};

export const discussImplementation = async (message: string, context?: string) => {
    const token = localStorage.getItem('token');
    const headers: HeadersInit = {
        'Content-Type': 'application/json',
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}/ai/discuss`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ message, context }),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to discuss implementation');
    }

    return response.json();
};
