import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Code2,
  Edit3,
  Flag,
  Zap,
  CheckCircle2,
  Circle,
  Layers,
  ArrowLeft,
  Share2,
} from 'lucide-react';
import type { FileCourse, FileLesson, UXLightChapter } from '../types';
import { UserMenu } from '../../components/UserMenu';

interface HeaderProps {
  course: FileCourse;
  chapters: UXLightChapter[];
  currentLesson: FileLesson;
  currentChapterIndex: number;
  currentLessonIndex: number;
  totalLessons: number;
  currentGlobalIndex: number;
  completedIds: Set<string>;
  totalXp: number;
  onSelectLesson: (chapterIndex: number, lessonIndex: number) => void;
  onPrevious: () => void;
  onNext: () => void;
  onOpenEmbed: () => void;
  onOpenStudio: () => void;
  onOpenFlag: () => void;
  onSwitchUi?: () => void;
  onShare?: () => void;
  canShare?: boolean;
  onShareBundle?: () => void;
}

export function Header({
  course,
  chapters,
  currentLesson,
  currentChapterIndex,
  currentLessonIndex,
  totalLessons,
  currentGlobalIndex,
  completedIds,
  totalXp,
  onSelectLesson,
  onPrevious,
  onNext,
  onOpenEmbed,
  onOpenStudio,
  onOpenFlag,
  onSwitchUi,
  onShare,
  canShare,
  onShareBundle,
}: HeaderProps) {
  const [isOutlineOpen, setIsOutlineOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOutlineOpen(false);
      }
    }
    if (isOutlineOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOutlineOpen]);

  const isPrevDisabled = currentGlobalIndex === 0;
  const isNextDisabled = currentGlobalIndex === totalLessons - 1;

  return (
    <header className="h-[56px] min-h-[56px] max-h-[56px] bg-white border-b border-[#e2e8ee] flex items-center justify-between px-2 sm:px-4 z-30 select-none shadow-sm">
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 group hover:opacity-90 transition-opacity shrink-0"
          title="Back to Courses"
        >
          <div className="w-8 h-8 rounded-lg bg-[#03ef62] flex items-center justify-center shadow-sm relative overflow-hidden group-hover:scale-105 transition-transform">
            <div className="w-4 h-4 bg-[#05192d] rotate-45 transform translate-x-[-1px]" />
            <div className="absolute w-2.5 h-2.5 bg-[#03ef62] rotate-45 transform translate-x-[3px]" />
          </div>
          <span className="font-extrabold text-[16px] sm:text-[18px] tracking-tight text-[#05192d] hidden sm:inline">
            UX Light
          </span>
        </button>

        <span className="text-[#93a3b4] text-sm hidden md:inline">/</span>

        <nav className="hidden md:flex items-center text-xs lg:text-sm text-[#5b6b7b] font-medium truncate">
          <span onClick={() => navigate('/')} className="hover:text-[#05192d] cursor-pointer transition-colors">
            Learn
          </span>
          <span className="text-[#93a3b4] mx-1.5">/</span>
          <span onClick={() => navigate('/')} className="hover:text-[#05192d] cursor-pointer transition-colors">
            Courses
          </span>
          <span className="text-[#93a3b4] mx-1.5">/</span>
          <span className="text-[#05192d] font-semibold truncate max-w-[120px] lg:max-w-[240px]">
            {course.title}
          </span>
        </nav>
      </div>

      <div className="flex items-center gap-1 sm:gap-2 relative min-w-0" ref={dropdownRef}>
        <button
          onClick={onPrevious}
          disabled={isPrevDisabled}
          className="w-8 h-8 rounded-md flex items-center justify-center text-[#5b6b7b] hover:text-[#05192d] hover:bg-[#f4f6f8] disabled:opacity-30 disabled:cursor-not-allowed transition-colors border border-[#e2e8ee] shrink-0"
          title="Previous lesson"
        >
          <ChevronLeft size={18} />
        </button>

        <button
          onClick={() => setIsOutlineOpen(!isOutlineOpen)}
          className={`flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 rounded-full text-xs font-semibold border transition-all min-w-0 ${
            isOutlineOpen
              ? 'bg-[#05192d] text-white border-[#05192d] shadow'
              : 'bg-[#f4f6f8] text-[#1a2733] border-[#e2e8ee] hover:border-[#93a3b4]'
          }`}
        >
          <Layers size={14} className={`shrink-0 ${isOutlineOpen ? 'text-[#03ef62]' : 'text-[#5b6b7b]'}`} />
          <span className="truncate max-w-[100px] sm:max-w-[180px] md:max-w-[260px]">
            {currentLesson.title}
          </span>
          <ChevronDown
            size={14}
            className={`shrink-0 transition-transform ${isOutlineOpen ? 'rotate-180 text-[#03ef62]' : 'text-[#5b6b7b]'}`}
          />
        </button>

        <button
          onClick={onNext}
          disabled={isNextDisabled}
          className="w-8 h-8 rounded-md flex items-center justify-center text-[#5b6b7b] hover:text-[#05192d] hover:bg-[#f4f6f8] disabled:opacity-30 disabled:cursor-not-allowed transition-colors border border-[#e2e8ee] shrink-0"
          title="Next lesson"
        >
          <ChevronRight size={18} />
        </button>

        {isOutlineOpen && (
          <div className="absolute top-[46px] left-1/2 -translate-x-1/2 w-[calc(100vw-24px)] sm:w-[460px] max-h-[70vh] bg-white border border-[#e2e8ee] rounded-xl shadow-2xl overflow-y-auto custom-scrollbar z-50">
            <div className="p-4 border-b border-[#e2e8ee] bg-[#f8fafc]">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-bold text-[#05192d] text-sm truncate">{course.title}</h3>
                  <p className="text-xs text-[#5b6b7b] mt-0.5">
                    {chapters.length} Chapters • {totalLessons} Lessons
                  </p>
                </div>
                <div className="flex items-center gap-1.5 bg-[#03ef62]/10 text-[#05192d] px-2.5 py-1 rounded-full border border-[#03ef62]/30 text-xs font-bold font-mono shrink-0">
                  <Zap size={13} className="text-[#02c852] fill-[#03ef62]" />
                  {totalXp} XP
                </div>
              </div>
            </div>

            <div className="p-3 space-y-4">
              {chapters.map((chapter, cIdx) => (
                <div key={chapter.id} className="space-y-1">
                  <div className="px-2 py-1 text-xs font-bold text-[#5b6b7b] uppercase tracking-wider">
                    {chapter.chapterNumber}. {chapter.title}
                  </div>
                  <div className="space-y-1">
                    {chapter.lessons.map((ex, eIdx) => {
                      const isSelected = cIdx === currentChapterIndex && eIdx === currentLessonIndex;
                      const isCompleted = completedIds.has(ex.slug);
                      return (
                        <button
                          key={ex.slug}
                          type="button"
                          onClick={() => {
                            onSelectLesson(cIdx, eIdx);
                            setIsOutlineOpen(false);
                          }}
                          className={`w-full flex items-center justify-between p-2.5 rounded-lg text-xs text-left transition-colors ${
                            isSelected
                              ? 'bg-[rgba(3,239,98,0.14)] text-[#05192d] font-bold border border-[#03ef62]/40'
                              : 'hover:bg-[#f4f6f8] text-[#1a2733] border border-transparent'
                          }`}
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            {isCompleted ? (
                              <CheckCircle2 size={16} className="text-[#03ef62] fill-[#03ef62]/20 shrink-0" />
                            ) : isSelected ? (
                              <div className="w-4 h-4 rounded-full border-2 border-[#03ef62] flex items-center justify-center shrink-0">
                                <div className="w-1.5 h-1.5 rounded-full bg-[#03ef62]" />
                              </div>
                            ) : (
                              <Circle size={16} className="text-[#93a3b4] shrink-0" />
                            )}
                            <span className="truncate">{ex.title}</span>
                          </div>
                          <span className="px-1.5 py-0.5 rounded bg-[#e2e8ee] text-[#5b6b7b] font-mono text-[10px] shrink-0 ml-2">
                            35 XP
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-1 sm:gap-2 shrink-0">
        <div className="hidden lg:flex items-center gap-1.5 px-3 py-1 bg-[#05192d] text-white rounded-full text-xs font-mono font-bold">
          <Zap size={14} className="text-[#03ef62] fill-[#03ef62]" />
          <span>{totalXp} XP</span>
        </div>
        <div className="w-px h-5 bg-[#e2e8ee] mx-1 hidden sm:block" />
        {onShareBundle && (
          <button
            onClick={onShareBundle}
            className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-semibold text-[#05192d] bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 transition-colors"
            title="Share & export this lesson or course"
          >
            <Share2 size={15} className="text-blue-600" />
            <span className="hidden md:inline">Share</span>
          </button>
        )}
        {canShare && onShare && (
          <button
            onClick={onShare}
            className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-semibold text-[#05192d] bg-[#03ef62]/15 hover:bg-[#03ef62]/25 border border-[#03ef62]/40 transition-colors"
            title="Share achievement card"
          >
            <Share2 size={15} />
            <span className="hidden md:inline">Achievement</span>
          </button>
        )}
        {onSwitchUi && (
          <button
            onClick={onSwitchUi}
            className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-semibold text-[#5b6b7b] hover:text-[#05192d] hover:bg-[#f4f6f8] border border-[#e2e8ee] transition-colors"
            title="Switch to the classic BaseLayer interface"
          >
            <Code2 size={15} />
            <span className="hidden md:inline">Classic UI</span>
          </button>
        )}
        <button
          onClick={onOpenEmbed}
          className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-semibold text-[#5b6b7b] hover:text-[#05192d] hover:bg-[#f4f6f8] border border-[#e2e8ee] transition-colors"
          title="Embed snippet"
        >
          <Code2 size={15} />
          <span className="hidden md:inline">Embed</span>
        </button>
        <button
          onClick={onOpenStudio}
          className="hidden sm:flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-semibold text-[#5b6b7b] hover:text-[#05192d] hover:bg-[#f4f6f8] border border-[#e2e8ee] transition-colors"
          title="Author Studio"
        >
          <Edit3 size={15} />
          <span className="hidden md:inline">Studio</span>
        </button>
        <button
          onClick={onOpenFlag}
          className="p-1.5 rounded-lg text-[#93a3b4] hover:text-[#ff6b6b] hover:bg-[#ffecec] transition-colors"
          title="Report an issue"
        >
          <Flag size={15} />
        </button>
        <button
          onClick={() => navigate('/')}
          className="p-1.5 rounded-lg text-[#5b6b7b] hover:text-[#05192d] hover:bg-[#f4f6f8] transition-colors"
          title="Back to courses"
        >
          <ArrowLeft size={16} />
        </button>
        <UserMenu variant="light" />
      </div>
    </header>
  );
}
