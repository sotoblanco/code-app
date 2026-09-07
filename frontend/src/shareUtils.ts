import { API_BASE_URL } from './config';

export interface ExportLessonBundle {
  title: string;
  slug: string;
  order: number;
  chapter?: string | null;
  exercise_type: string;
  language: string;
  description: string;
  initial_code: string;
  test_code: string;
  solution_code: string;
  skills: string[];
  google_sheet_id?: string | null;
  copy_on_open?: boolean;
  stroke_color?: string;
  stroke_width?: number;
  hints?: string[];
  question_image_base64?: string | null;
  solution_image_base64?: string | null;
}

export interface ExportCourseBundle {
  version: number;
  kind: 'course';
  slug: string;
  title: string;
  description: string;
  skills: string[];
  lessons: ExportLessonBundle[];
}

export interface SingleLessonShareBundle {
  version: number;
  kind: 'lesson';
  course_slug: string;
  lesson: ExportLessonBundle;
}

export type AnyShareBundle = ExportCourseBundle | SingleLessonShareBundle;

export interface ImportBundleRequest {
  version: number;
  kind: 'course' | 'lesson';
  slug?: string | null;
  title?: string | null;
  description?: string | null;
  skills?: string[];
  lessons?: ExportLessonBundle[];
  lesson?: ExportLessonBundle | null;
  target_course_slug?: string | null;
}

export interface ImportBundleResponse {
  status: string;
  kind: 'course' | 'lesson';
  course_slug: string;
  lesson_slug: string;
  title: string;
  lesson_count: number;
  message: string;
}

export const MAX_SHARE_URL_CHARS = 16_000;

export async function fetchCourseExport(slug: string): Promise<ExportCourseBundle> {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE_URL}/file-courses/${slug}/export`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to export course ${slug}`);
  }
  return res.json();
}

export async function fetchLessonExport(
  courseSlug: string,
  lessonSlug: string
): Promise<SingleLessonShareBundle> {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE_URL}/file-courses/${courseSlug}/${lessonSlug}/export`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to export lesson ${lessonSlug}`);
  }
  return res.json();
}

export async function postImportBundle(
  bundle: ImportBundleRequest
): Promise<ImportBundleResponse> {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE_URL}/file-courses/import`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(bundle),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to import bundle');
  }
  return res.json();
}

export function downloadJsonFile(filename: string, data: object): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename.endsWith('.json') ? filename : `${filename}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export async function compressToUrlSafe(text: string): Promise<string> {
  if (typeof CompressionStream !== 'undefined') {
    try {
      const stream = new Blob([text]).stream().pipeThrough(new CompressionStream('deflate'));
      const buffer = await new Response(stream).arrayBuffer();
      const bytes = new Uint8Array(buffer);
      let binary = '';
      for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
      }
      return 'c:' + btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    } catch {
      // Fallback
    }
  }
  return 'u:' + btoa(encodeURIComponent(text)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export async function decompressFromUrlSafe(encoded: string): Promise<string> {
  if (!encoded) return '';

  const isCompressed = encoded.startsWith('c:');
  const raw = encoded.startsWith('c:') || encoded.startsWith('u:') ? encoded.slice(2) : encoded;
  let base64 = raw.replace(/-/g, '+').replace(/_/g, '/');
  while (base64.length % 4) base64 += '=';

  if (isCompressed && typeof DecompressionStream !== 'undefined') {
    try {
      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }
      const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate'));
      return await new Response(stream).text();
    } catch {
      // Fallback
    }
  }
  return decodeURIComponent(atob(base64));
}
