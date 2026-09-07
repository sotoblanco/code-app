import { API_BASE_URL } from '../config';

export interface ChatTurn {
    role: 'user' | 'assistant';
    content: string;
}

export type TutorStyleId = 'solveit' | 'socratic' | 'direct' | 'blooms';

/**
 * Sends the accumulated conversation to SocratiQ.
 *
 * @param messages Ordered prior turns (oldest first) WITHOUT the canned greeting.
 *   The server owns the system prompt and trims/bounds the history itself.
 * @param context Stable per-session exercise context (lesson + current code).
 *   Never includes test.py / solution content.
 * @param tutorStyle Optional explicit style override for this request. When
 *   omitted the server uses the learner's LEARNING.md profile as the source of
 *   truth. The in-app control only sends this after persisting the choice to
 *   the profile via `emitLearnerEvent`.
 */
export const discussImplementation = async (
    messages: ChatTurn[],
    context?: string,
    tutorStyle?: TutorStyleId,
) => {
    const token = localStorage.getItem('token');
    if (!token) {
        throw new Error('Please sign in to use the tutor.');
    }
    const headers: HeadersInit = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
    };

    const response = await fetch(`${API_BASE_URL}/ai/discuss`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
            messages,
            context,
            tutor_style: tutorStyle,
        }),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to discuss implementation');
    }

    return response.json();
};

export interface AIProviderInfo {
    id: string;
    name: string;
    needs_key: boolean;
    default_model: string;
    default_base: string | null;
    docs_url: string;
    blurb: string;
    group: 'free' | 'key' | string;
    suggested_models?: string[];
}

export interface AIStatus {
    configured: boolean;
    has_key: boolean;
    provider?: string;
    model: string;
    api_base?: string | null;
    providers?: AIProviderInfo[];
}

export interface ConfigureKeyResult {
    success: boolean;
    message: string;
    saved_to_file: boolean;
    provider?: string;
    model?: string;
}

export interface ConfigureAiRequest {
    provider: string;
    api_key?: string;
    model?: string;
    api_base?: string;
}

export const getAiStatus = async (): Promise<AIStatus> => {
    const response = await fetch(`${API_BASE_URL}/ai/status`);
    if (!response.ok) {
        throw new Error('Failed to fetch AI status');
    }
    return response.json();
};

export const configureAiKey = async (
    body: ConfigureAiRequest | string,
): Promise<ConfigureKeyResult> => {
    const token = localStorage.getItem('token');
    const headers: HeadersInit = {
        'Content-Type': 'application/json',
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const payload =
        typeof body === 'string'
            ? { provider: 'gemini', api_key: body }
            : {
                  provider: body.provider,
                  api_key: body.api_key || '',
                  model: body.model || undefined,
                  api_base: body.api_base || undefined,
              };

    const response = await fetch(`${API_BASE_URL}/ai/configure-key`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to configure AI key');
    }

    return response.json();
};

export interface ToolTraceItem {
    tool_name: string;
    status: string;
    input_summary: string;
    output_summary: string;
    details?: Record<string, unknown>;
}

export interface BuildCourseResult {
    slug: string;
    title: string;
    description?: string;
    narrative_arc?: string;
    lesson_count: number;
    grounded_in: string[];
    tool_traces?: ToolTraceItem[];
    solveit_compliance?: Record<string, boolean>;
}

export interface LessonVerificationStatus {
    order: number;
    title: string;
    status: string;
    solution_passes: boolean;
    starter_fails: boolean;
    detail?: string;
}

export interface ImportCourseResult extends BuildCourseResult {
    verified?: boolean;
    lesson_verifications?: LessonVerificationStatus[];
}

export const buildLearningCourse = async (
    topic: string,
    referenceText?: string,
): Promise<BuildCourseResult> => {
    const token = localStorage.getItem('token');
    if (!token) {
        throw new Error('Please start a learner session before building a course.');
    }

    const resources = referenceText?.trim()
        ? [{ kind: 'pasted-notes', name: 'Learner-provided notes', text: referenceText.trim() }]
        : [];
    const response = await fetch(`${API_BASE_URL}/ai/learning-path/build`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ topic: topic.trim(), resources }),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Could not build the learning course');
    }
    return response.json();
};

/**
 * Dead-simple, no-LLM path: generate the copy-paste instruction prompt for a
 * topic. The learner pastes this into any free chat and pastes the reply back
 * into {@link importLearningCourse}.
 */
export const getCourseBuildInstructions = async (
    topic: string,
    referenceText?: string,
): Promise<string> => {
    const token = localStorage.getItem('token');
    if (!token) {
        throw new Error('Please start a learner session before building a course.');
    }

    const resources = referenceText?.trim()
        ? [{ kind: 'pasted-notes', name: 'Learner-provided notes', text: referenceText.trim() }]
        : [];
    const response = await fetch(`${API_BASE_URL}/ai/learning-path/instructions`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ topic: topic.trim(), resources }),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Could not generate the build instructions');
    }
    const data = await response.json();
    return data.instructions as string;
};

/** Import a chat model's pasted reply as a verified course. No AI key needed. */
export const importLearningCourse = async (
    topic: string,
    responseText: string,
): Promise<ImportCourseResult> => {
    const token = localStorage.getItem('token');
    if (!token) {
        throw new Error('Please start a learner session before building a course.');
    }

    const response = await fetch(`${API_BASE_URL}/ai/learning-path/import`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ topic: topic.trim(), response_markdown: responseText }),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Could not import the course');
    }
    return response.json();
};
