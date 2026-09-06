import { useEffect } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';

export interface LessonLike {
  slug: string;
}

export interface ChapterLike {
  lessons: LessonLike[];
}

export function findLessonPosition(
  chapters: ChapterLike[],
  lessonSlug: string | null | undefined
): { chapterIndex: number; lessonIndex: number } | null {
  if (!chapters || !lessonSlug) return null;
  for (let chapterIndex = 0; chapterIndex < chapters.length; chapterIndex++) {
    const lessons = chapters[chapterIndex].lessons;
    for (let lessonIndex = 0; lessonIndex < lessons.length; lessonIndex++) {
      if (lessons[lessonIndex].slug === lessonSlug) {
        return { chapterIndex, lessonIndex };
      }
    }
  }
  return null;
}

export function lessonUrl(courseSlug: string, targetLessonSlug: string, search: string): string {
  return `/file-course/${courseSlug}/${targetLessonSlug}${search}`;
}

/**
 * Keeps a player's current (chapter, lesson) position in sync with the route
 * `/file-course/:slug/:lessonSlug`:
 *  - the URL always reflects the displayed lesson (so refresh/share/bookmark work),
 *  - external URL changes (back/forward, pasted deep link) move the displayed lesson.
 */
export function useLessonUrlSync(opts: {
  courseSlug?: string;
  chapters: ChapterLike[];
  currentChapterIndex: number;
  currentLessonIndex: number;
  onSelectLesson: (chapterIndex: number, lessonIndex: number) => void;
}) {
  const { lessonSlug: routeLessonSlug } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const current = opts.chapters[opts.currentChapterIndex]?.lessons[opts.currentLessonIndex];

  useEffect(() => {
    const slug = current?.slug;
    if (!opts.courseSlug || !slug) return;
    if (slug === routeLessonSlug) return;
    navigate(lessonUrl(opts.courseSlug, slug, location.search), { replace: true });
  }, [opts.courseSlug, current?.slug, routeLessonSlug, location.search]);

  useEffect(() => {
    if (!opts.chapters.length || !opts.courseSlug) return;
    if (!routeLessonSlug) return; // handled by the URL-reflect effect above
    const target = findLessonPosition(opts.chapters, routeLessonSlug);
    if (!target) {
      if (current?.slug) {
        navigate(lessonUrl(opts.courseSlug, current.slug, location.search), { replace: true });
      }
      return;
    }
    if (
      target.chapterIndex === opts.currentChapterIndex &&
      target.lessonIndex === opts.currentLessonIndex
    ) {
      return;
    }
    opts.onSelectLesson(target.chapterIndex, target.lessonIndex);
  }, [routeLessonSlug]);
}
