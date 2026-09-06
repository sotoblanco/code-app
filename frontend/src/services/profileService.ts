import { API_BASE_URL } from '../config';

export interface ProfileFrontMatter {
  username: string;
  updated_at: string;
  version: number;
  preferred_ui: 'classic' | 'light';
  tutor_style: 'solveit' | 'socratic' | 'direct' | 'blooms';
  tone?: 'direct' | 'pragmatic' | 'concise';
  understanding_level: 'beginner' | 'intermediate' | 'advanced';
  preferred_modalities: string[];
  pace: 'unhurried' | 'sprint' | 'mixed';
  explanation_length?: 'short' | 'thorough';
  exercise_format?: 'micro_steps' | 'macro_challenges' | 'guided_completion';
}

export interface LearningProfileData {
  frontmatter: ProfileFrontMatter;
  snapshot: string;
  courses_taken: string[];
  courses_built: string[];
  signals: string[];
  customize_next: string[];
}

export interface LearningProfileResponse {
  markdown: string;
  parsed: LearningProfileData;
}

async function parseJsonResponse<T>(response: Response, fallbackError: string): Promise<T> {
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    const text = await response.text();
    if (text.startsWith('<!doctype') || text.startsWith('<html')) {
      throw new Error(
        'The backend API server returned HTML instead of JSON. Ensure the backend server is running and /me routes are proxied.'
      );
    }
    throw new Error(text || fallbackError);
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || fallbackError);
  }

  return response.json();
}

export const getLearningProfile = async (): Promise<LearningProfileResponse> => {
  const token = localStorage.getItem('token');
  if (!token) {
    throw new Error('Please sign in to view your learning profile.');
  }

  const response = await fetch(`${API_BASE_URL}/me/learning-profile`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  return parseJsonResponse<LearningProfileResponse>(response, 'Failed to fetch learning profile');
};

export const updateLearningProfile = async (
  markdown: string
): Promise<LearningProfileResponse> => {
  const token = localStorage.getItem('token');
  if (!token) {
    throw new Error('Please sign in to update your learning profile.');
  }

  const response = await fetch(`${API_BASE_URL}/me/learning-profile`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ markdown }),
  });

  return parseJsonResponse<LearningProfileResponse>(response, 'Failed to update learning profile');
};

export const emitLearnerEvent = async (
  eventType: string,
  payload: Record<string, unknown>
): Promise<void> => {
  const token = localStorage.getItem('token');
  if (!token) return;

  try {
    await fetch(`${API_BASE_URL}/me/learning-profile/events`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ event_type: eventType, payload }),
    });
  } catch {
    // Non-blocking telemetry
  }
};

export interface CourseProgressSummary {
  course_slug: string;
  resume_lesson: string | null;
  resume_order: number | null;
  resume_title: string | null;
  completed_lessons: string[];
  completed: boolean;
  done_count: number;
  xp: number;
  lesson_count: number | null;
}

export const fetchMyProgress = async (): Promise<CourseProgressSummary[]> => {
  const token = localStorage.getItem('token');
  if (!token) return [];

  try {
    const response = await fetch(`${API_BASE_URL}/me/progress`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return [];
    const data = await response.json();
    return Array.isArray(data?.courses) ? data.courses : [];
  } catch {
    return [];
  }
};

export interface LearnerQuestionnaire {
  intake_preference?: 'diagram' | 'table' | 'hands_on' | 'story';
  explanation_length?: 'short' | 'thorough';
  exercise_format?: 'micro_steps' | 'macro_challenges' | 'guided_completion';
  hint_preference?: 'toy_example' | 'guiding_question' | 'direct_explanation';
  goal?: string;
  preferred_modalities?: string[];
  understanding_level?: 'beginner' | 'intermediate' | 'advanced';
  tutor_style?: 'solveit' | 'socratic' | 'direct' | 'blooms';
  tone?: 'direct' | 'pragmatic' | 'concise';
  pace?: 'unhurried' | 'sprint' | 'mixed';
  preferred_ui?: 'classic' | 'light';
  custom_notes?: string;
}

export const submitLearnerQuestionnaire = async (
  answers: LearnerQuestionnaire
): Promise<LearningProfileResponse> => {
  const token = localStorage.getItem('token');
  if (!token) {
    throw new Error('Please sign in to customize your learning profile.');
  }

  const response = await fetch(`${API_BASE_URL}/me/learning-profile/questionnaire`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(answers),
  });

  return parseJsonResponse<LearningProfileResponse>(response, 'Failed to submit questionnaire');
};

