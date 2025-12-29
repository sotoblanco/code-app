import { API_BASE_URL } from '../config';

export const generateExercise = async (prompt: string) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE_URL}/ai/generate/exercise`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ prompt }),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to generate exercise');
    }

    return response.json();
};

export const discussImplementation = async (message: string, context?: string) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE_URL}/ai/discuss`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ message, context }),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to discuss implementation');
    }

    return response.json();
};
