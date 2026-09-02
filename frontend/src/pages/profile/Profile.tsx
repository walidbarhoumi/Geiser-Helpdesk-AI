import React, { useState, useEffect } from 'react';
import {
  User, Mail, Shield, Calendar, Key, Bell, Bot, Edit3,
  Zap, TrendingUp, Clock, Star, Lock, Smartphone,
  Globe, MapPin, ChevronRight, Activity, Award,
  BarChart2, Cpu, AlertTriangle, Eye,
} from 'lucide-react';

import { useAuth } from '../../store/authContext';
import { format } from 'date-fns';

/* ─────────────────────────────────────────────
   Animated Counter
───────────────────────────────────────────── */
const Counter: React.FC<{ to: number; suffix?: string; duration?: number }> = ({
  to, suffix = '', duration = 1400,
}) => {
  const [val, setVal] = useState(0);
  useEffect(() => {
    let start = 0;
    const step = to / (duration / 16);
    const id = setInterval(() => {
      start += step;
      if (start >= to) { setVal(to); clearInterval(id); } else setVal(Math.floor(start));
    }, 16);
    return () => clearInterval(id);
  }, [to, duration]);
  return <>{val}{suffix}</>;
};

/* ─────────────────────────────────────────────
   MAIN COMPONENT
───────────────────────────────────────────── */
const Profile: React.FC = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'overview' | 'analytics' | 'security'>('overview');

  if (!user) return null;

  const initial   = user.full_name?.charAt(0)?.toUpperCase() || 'U';
  const memberSince = format(new Date(user.created_at), 'MMM yyyy');
  const joinedFull  = format(new Date(user.created_at), 'MMMM dd, yyyy');

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');

        /* ── RESET & ROOT ── */
        .p2-root *, .p2-root *::before, .p2-root *::after { box-sizing: border-box; margin: 0; padding: 0; }

        .p2-root {
          font-family: 'DM Sans', sans-serif;
          background: #06060f;
          min-height: 100vh;
          color: #fff;
          position: relative;
          overflow-x: hidden;
        }

        /* ── AMBIENT CANVAS ── */
        .p2-ambient {
          position: fixed; inset: 0; pointer-events: none; z-index: 0;
          background:
            radial-gradient(ellipse 70% 50% at 75% 5%,  rgba(109,40,217,0.18) 0%, transparent 65%),
            radial-gradient(ellipse 55% 40% at 5%  70%,  rgba(79,70,229,0.10) 0%, transparent 60%),
            radial-gradient(ellipse 40% 60% at 50% 100%, rgba(139,92,246,0.07) 0%, transparent 55%);
        }

        /* ── HERO BANNER ── */
        .p2-hero {
          position: relative; z-index: 1;
          height: 260px; overflow: hidden;
          background: linear-gradient(160deg, #0a0a1e 0%, #0f0b28 45%, #080814 100%);
        }

        .p2-hero-grid {
          position: absolute; inset: 0;
          background-image:
            linear-gradient(rgba(139,92,246,0.06) 1px, transparent 1px),
            linear-gradient(90deg, rgba(139,92,246,0.06) 1px, transparent 1px);
          background-size: 44px 44px;
          mask-image: radial-gradient(ellipse 90% 80% at 50% 50%, black 30%, transparent 100%);
        }

        .p2-hero-glow-l {
          position: absolute; left: -100px; top: -60px;
          width: 500px; height: 500px;
          background: radial-gradient(circle, rgba(109,40,217,0.28) 0%, transparent 65%);
          filter: blur(60px);
        }

        .p2-hero-glow-r {
          position: absolute; right: -80px; bottom: -100px;
          width: 400px; height: 400px;
          background: radial-gradient(circle, rgba(79,70,229,0.16) 0%, transparent 65%);
          filter: blur(50px);
        }

        /* ── HERO IDENTITY ROW ── */
        .p2-identity {
          position: relative; z-index: 2;
          padding: 0 48px;
          margin-top: -70px;
          display: flex;
          align-items: flex-end;
          gap: 28px;
          flex-wrap: wrap;
        }

        .p2-avatar-frame {
          position: relative; flex-shrink: 0;
        }

        .p2-avatar-ring {
          position: absolute; inset: -4px;
          border-radius: 26px;
          background: linear-gradient(135deg, #7c3aed, #4f46e5, #7c3aed);
          background-size: 200% 200%;
          animation: p2RingRotate 4s linear infinite;
        }

        @keyframes p2RingRotate {
          0%   { background-position: 0%   50%; }
          50%  { background-position: 100% 50%; }
          100% { background-position: 0%   50%; }
        }

        .p2-avatar {
          position: relative;
          width: 112px; height: 112px;
          border-radius: 22px;
          background: linear-gradient(135deg, #5b21b6 0%, #4338ca 100%);
          display: flex; align-items: center; justify-content: center;
          font-family: 'DM Serif Display', serif;
          font-size: 46px; color: #fff;
          border: 3px solid #06060f;
          z-index: 1;
          box-shadow: 0 12px 40px rgba(109,40,217,0.5);
        }

        .p2-pulse {
          position: absolute; bottom: 6px; right: 6px; z-index: 2;
          width: 16px; height: 16px; border-radius: 50%;
          background: #10b981;
          border: 2.5px solid #06060f;
          box-shadow: 0 0 12px #10b981;
          animation: p2Pulse 2.4s ease-in-out infinite;
        }

        @keyframes p2Pulse {
          0%,100% { box-shadow: 0 0 8px #10b981; transform: scale(1); }
          50%      { box-shadow: 0 0 18px #10b981cc; transform: scale(1.1); }
        }

        .p2-id-info { flex: 1; padding-bottom: 10px; min-width: 240px; }

        .p2-name {
          font-family: 'DM Serif Display', serif;
          font-size: 34px; letter-spacing: -0.5px; color: #fff;
          line-height: 1.1; margin-bottom: 6px;
        }

        .p2-title {
          font-size: 13px; color: rgba(255,255,255,0.4); margin-bottom: 12px;
          letter-spacing: 0.3px;
        }

        .p2-badges { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 18px; }

        .p2-badge {
          font-size: 10.5px; padding: 4px 11px; border-radius: 6px; font-weight: 500;
          letter-spacing: 0.3px;
        }

        .p2-badge-role   { background: rgba(109,40,217,0.18); color: #c4b5fd; border: 1px solid rgba(109,40,217,0.3); }
        .p2-badge-status { background: rgba(16,185,129,0.13); color: #6ee7b7;  border: 1px solid rgba(16,185,129,0.25); }
        .p2-badge-award  { background: rgba(245,158,11,0.12); color: #fcd34d;  border: 1px solid rgba(245,158,11,0.22); }

        .p2-hero-kpis { display: flex; gap: 32px; flex-wrap: wrap; }

        .p2-kpi { display: flex; flex-direction: column; gap: 3px; }

        .p2-kpi-num {
          font-family: 'DM Serif Display', serif;
          font-size: 26px; line-height: 1; color: #fff;
        }

        .p2-kpi-lbl {
          font-size: 10px; text-transform: uppercase; letter-spacing: 0.8px;
          color: rgba(255,255,255,0.3);
        }

        /* ── SCORE PILL ── */
        .p2-score-pill {
          position: absolute; top: 24px; right: 48px; z-index: 2;
          display: flex; align-items: center; gap: 10px;
          padding: 10px 18px;
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(139,92,246,0.25);
          border-radius: 14px;
          backdrop-filter: blur(14px);
          box-shadow: 0 4px 30px rgba(109,40,217,0.15), inset 0 1px 0 rgba(255,255,255,0.06);
        }

        .p2-score-num {
          font-family: 'DM Serif Display', serif;
          font-size: 28px; color: #fff; line-height: 1;
        }

        .p2-score-detail { display: flex; flex-direction: column; gap: 1px; }
        .p2-score-label  { font-size: 10px; color: rgba(255,255,255,0.35); letter-spacing: 0.7px; text-transform: uppercase; }
        .p2-score-rank   { font-size: 11px; color: #a78bfa; font-weight: 500; }

        /* ── TABS ── */
        .p2-tabs-bar {
          position: relative; z-index: 1;
          padding: 28px 48px 0;
          display: flex; gap: 4px; border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        .p2-tab {
          padding: 10px 20px; font-size: 13px; font-weight: 500;
          color: rgba(255,255,255,0.35);
          background: transparent; border: none; border-bottom: 2px solid transparent;
          cursor: pointer; margin-bottom: -1px; transition: all 0.2s;
          font-family: 'DM Sans', sans-serif; letter-spacing: 0.2px;
        }

        .p2-tab:hover { color: rgba(255,255,255,0.7); }

        .p2-tab-active {
          color: #c4b5fd !important;
          border-bottom-color: #7c3aed !important;
        }

        /* ── LAYOUT ── */
        .p2-body {
          position: relative; z-index: 1;
          padding: 32px 48px 56px;
          display: grid;
          grid-template-columns: 1fr 300px;
          gap: 22px;
          align-items: start;
        }

        .p2-main { display: flex; flex-direction: column; gap: 18px; }
        .p2-side  { display: flex; flex-direction: column; gap: 18px; }

        /* ── GLASS CARD ── */
        .p2-card {
          background: rgba(255,255,255,0.025);
          border: 1px solid rgba(255,255,255,0.065);
          border-radius: 20px;
          padding: 26px;
          transition: border-color 0.3s, box-shadow 0.3s;
          backdrop-filter: blur(12px);
        }

        .p2-card:hover {
          border-color: rgba(139,92,246,0.18);
          box-shadow: 0 0 0 1px rgba(139,92,246,0.06), 0 8px 32px rgba(0,0,0,0.3);
        }

        .p2-card-hd {
          display: flex; align-items: center; justify-content: space-between;
          margin-bottom: 20px;
        }

        .p2-card-title {
          font-size: 10px; letter-spacing: 1.8px; text-transform: uppercase;
          color: rgba(255,255,255,0.25); font-weight: 600;
        }

        .p2-card-action {
          font-size: 11px; color: #7c3aed; cursor: pointer;
          display: flex; align-items: center; gap: 4px;
          border: none; background: none; font-family: 'DM Sans', sans-serif;
          transition: color 0.2s;
        }

        .p2-card-action:hover { color: #a78bfa; }

        /* ── AI INSIGHT BANNER ── */
        .p2-ai-banner {
          position: relative;
          background: linear-gradient(120deg, rgba(109,40,217,0.12) 0%, rgba(79,70,229,0.08) 100%);
          border: 1px solid rgba(139,92,246,0.22);
          border-radius: 16px; padding: 18px 22px;
          display: flex; align-items: flex-start; gap: 14px;
          overflow: hidden;
        }

        .p2-ai-banner::before {
          content: '';
          position: absolute; top: 0; left: 0; right: 0; height: 1px;
          background: linear-gradient(90deg, transparent, rgba(139,92,246,0.5), transparent);
        }

        .p2-ai-icon-wrap {
          width: 38px; height: 38px; border-radius: 10px; flex-shrink: 0;
          background: rgba(109,40,217,0.2); border: 1px solid rgba(109,40,217,0.3);
          display: flex; align-items: center; justify-content: center; color: #a78bfa;
          position: relative;
        }

        .p2-ai-icon-wrap::after {
          content: '';
          position: absolute; top: -3px; right: -3px;
          width: 8px; height: 8px; border-radius: 50%;
          background: #7c3aed;
          box-shadow: 0 0 8px #7c3aed;
          animation: p2Pulse 2.4s ease-in-out infinite;
        }

        .p2-ai-text { flex: 1; }
        .p2-ai-label { font-size: 10px; color: #7c3aed; font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 4px; }
        .p2-ai-msg   { font-size: 13.5px; color: rgba(255,255,255,0.75); line-height: 1.55; }

        /* ── INFO GRID ── */
        .p2-info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 13px; }

        .p2-field-label { font-size: 10px; letter-spacing: 1.1px; text-transform: uppercase; color: rgba(255,255,255,0.22); margin-bottom: 6px; }

        .p2-field-val {
          display: flex; align-items: center; gap: 11px;
          padding: 12px 15px;
          background: rgba(255,255,255,0.022);
          border: 1px solid rgba(255,255,255,0.055);
          border-radius: 12px;
          transition: border-color 0.2s, background 0.2s;
          cursor: default;
        }

        .p2-field-val:hover {
          border-color: rgba(139,92,246,0.2);
          background: rgba(139,92,246,0.04);
        }

        .p2-field-icon { color: rgba(255,255,255,0.22); flex-shrink: 0; }
        .p2-field-text { font-size: 13px; color: rgba(255,255,255,0.7); }

        /* ── EDIT BTN ── */
        .p2-edit-btn {
          display: inline-flex; align-items: center; gap: 8px;
          margin-top: 18px; padding: 12px 22px;
          background: rgba(109,40,217,0.1);
          border: 1px solid rgba(109,40,217,0.25);
          border-radius: 12px;
          font-family: 'DM Sans', sans-serif;
          font-size: 13px; font-weight: 500; color: #a78bfa;
          cursor: pointer; transition: all 0.22s;
        }

        .p2-edit-btn:hover {
          background: rgba(109,40,217,0.2);
          border-color: rgba(139,92,246,0.45);
          color: #c4b5fd;
          transform: translateY(-1px);
          box-shadow: 0 6px 24px rgba(109,40,217,0.2);
        }

        /* ── SKILLS ── */
        .p2-skills-wrap { display: flex; flex-wrap: wrap; gap: 9px; }

        .p2-skill {
          display: flex; align-items: center; gap: 8px;
          padding: 8px 14px; border-radius: 10px;
          background: rgba(255,255,255,0.03);
          border: 1px solid rgba(255,255,255,0.07);
          font-size: 12px; font-weight: 500; color: rgba(255,255,255,0.62);
          transition: all 0.2s;
          cursor: default;
        }

        .p2-skill:hover {
          border-color: rgba(139,92,246,0.3);
          background: rgba(109,40,217,0.1);
          color: #c4b5fd;
          transform: translateY(-1px);
        }

        .p2-skill-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }

        /* ── ANALYTICS GRID ── */
        .p2-analytics-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 13px; }

        .p2-metric-card {
          background: rgba(255,255,255,0.02);
          border: 1px solid rgba(255,255,255,0.058);
          border-radius: 16px; padding: 18px;
          transition: all 0.25s;
          position: relative; overflow: hidden;
        }

        .p2-metric-card::before {
          content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
          opacity: 0; transition: opacity 0.3s;
        }

        .p2-metric-card:hover { border-color: rgba(139,92,246,0.22); transform: translateY(-2px); }
        .p2-metric-card:hover::before { opacity: 1; }

        .p2-metric-card.purple::before { background: linear-gradient(90deg, transparent, #7c3aed, transparent); }
        .p2-metric-card.green::before  { background: linear-gradient(90deg, transparent, #10b981, transparent); }
        .p2-metric-card.amber::before  { background: linear-gradient(90deg, transparent, #f59e0b, transparent); }
        .p2-metric-card.blue::before   { background: linear-gradient(90deg, transparent, #3b82f6, transparent); }

        .p2-metric-icon {
          width: 34px; height: 34px; border-radius: 9px;
          display: flex; align-items: center; justify-content: center;
          margin-bottom: 14px;
        }

        .p2-metric-icon.purple { background: rgba(109,40,217,0.15); border: 1px solid rgba(109,40,217,0.22); color: #a78bfa; }
        .p2-metric-icon.green  { background: rgba(16,185,129,0.12);  border: 1px solid rgba(16,185,129,0.2);  color: #6ee7b7; }
        .p2-metric-icon.amber  { background: rgba(245,158,11,0.12);  border: 1px solid rgba(245,158,11,0.2);  color: #fcd34d; }
        .p2-metric-icon.blue   { background: rgba(59,130,246,0.12);  border: 1px solid rgba(59,130,246,0.2);  color: #93c5fd; }

        .p2-metric-val  { font-family: 'DM Serif Display', serif; font-size: 28px; color: #fff; line-height: 1; margin-bottom: 4px; }
        .p2-metric-lbl  { font-size: 11px; color: rgba(255,255,255,0.32); text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 12px; }
        .p2-metric-bar  { height: 2px; background: rgba(255,255,255,0.05); border-radius: 1px; overflow: hidden; }
        .p2-metric-fill { height: 100%; border-radius: 1px; transition: width 1s cubic-bezier(0.16,1,0.3,1); }

        .p2-metric-fill.purple { background: linear-gradient(to right, #5b21b6, #7c3aed); }
        .p2-metric-fill.green  { background: linear-gradient(to right, #065f46, #10b981); }
        .p2-metric-fill.amber  { background: linear-gradient(to right, #92400e, #f59e0b); }
        .p2-metric-fill.blue   { background: linear-gradient(to right, #1d4ed8, #3b82f6); }

        /* ── PERF BARS ── */
        .p2-perf-row { display: flex; align-items: center; gap: 14px; padding: 11px 0; border-bottom: 1px solid rgba(255,255,255,0.04); }
        .p2-perf-row:last-child { border-bottom: none; }
        .p2-perf-lbl  { font-size: 12px; color: rgba(255,255,255,0.4); width: 160px; flex-shrink: 0; }
        .p2-perf-track { flex: 1; height: 3px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; }
        .p2-perf-bar   { height: 100%; border-radius: 2px; transition: width 1.2s cubic-bezier(0.16,1,0.3,1); }
        .p2-perf-pct   { font-size: 12px; font-weight: 500; color: rgba(255,255,255,0.65); width: 38px; text-align: right; }

        /* ── TIMELINE ── */
        .p2-tl { position: relative; padding-left: 20px; }
        .p2-tl-spine { position: absolute; left: 6px; top: 8px; bottom: 8px; width: 1px; background: rgba(255,255,255,0.06); }

        .p2-tl-item { position: relative; padding: 0 0 20px 20px; }
        .p2-tl-item:last-child { padding-bottom: 0; }

        .p2-tl-dot { position: absolute; left: -14px; top: 4px; width: 10px; height: 10px; border-radius: 50%; }
        .p2-tl-dot.purple { background: #7c3aed; box-shadow: 0 0 10px #7c3aed99; }
        .p2-tl-dot.green  { background: #10b981; box-shadow: 0 0 10px #10b98199; }
        .p2-tl-dot.amber  { background: #f59e0b; box-shadow: 0 0 10px #f59e0b99; }
        .p2-tl-dot.blue   { background: #3b82f6; box-shadow: 0 0 10px #3b82f699; }

        .p2-tl-title { font-size: 13px; color: rgba(255,255,255,0.78); font-weight: 500; margin-bottom: 3px; }
        .p2-tl-meta  { font-size: 11px; color: rgba(255,255,255,0.28); }

        /* ── SECURITY ── */
        .p2-sec-score {
          display: flex; align-items: center; gap: 18px;
          padding: 16px; border-radius: 14px;
          background: rgba(16,185,129,0.06);
          border: 1px solid rgba(16,185,129,0.14);
          margin-bottom: 20px;
        }

        .p2-sec-ring {
          position: relative; width: 62px; height: 62px;
          display: flex; align-items: center; justify-content: center; flex-shrink: 0;
        }

        .p2-sec-ring svg { position: absolute; top: 0; left: 0; transform: rotate(-90deg); }

        .p2-sec-ring-num {
          font-family: 'DM Serif Display', serif;
          font-size: 20px; color: #fff; line-height: 1; z-index: 1;
        }

        .p2-sec-info .p2-sec-name  { font-size: 14px; color: #fff; font-weight: 600; margin-bottom: 3px; }
        .p2-sec-info .p2-sec-desc  { font-size: 11px; color: rgba(255,255,255,0.38); }

        .p2-sec-row {
          display: flex; align-items: center; justify-content: space-between;
          padding: 13px 0; border-bottom: 1px solid rgba(255,255,255,0.04);
        }

        .p2-sec-row:last-child { border-bottom: none; }

        .p2-sec-left { display: flex; align-items: center; gap: 13px; }

        .p2-sec-icon {
          width: 36px; height: 36px; border-radius: 9px;
          display: flex; align-items: center; justify-content: center; flex-shrink: 0;
        }

        .p2-sec-icon.amber  { background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.18); color: #fcd34d; }
        .p2-sec-icon.purple { background: rgba(109,40,217,0.1); border: 1px solid rgba(109,40,217,0.2); color: #a78bfa; }
        .p2-sec-icon.blue   { background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.18); color: #93c5fd; }
        .p2-sec-icon.green  { background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.18); color: #6ee7b7; }

        .p2-sec-label { font-size: 13px; color: rgba(255,255,255,0.75); font-weight: 500; margin-bottom: 2px; }
        .p2-sec-sub   { font-size: 11px; color: rgba(255,255,255,0.28); }

        .p2-sec-badge {
          font-size: 10.5px; padding: 4px 10px; border-radius: 6px; font-weight: 500;
        }

        .p2-sec-badge.on    { background: rgba(16,185,129,0.12); color: #6ee7b7;  border: 1px solid rgba(16,185,129,0.22); }
        .p2-sec-badge.off   { background: rgba(255,255,255,0.05); color: rgba(255,255,255,0.4);  border: 1px solid rgba(255,255,255,0.09); }
        .p2-sec-badge.risk  { background: rgba(245,158,11,0.12); color: #fcd34d;  border: 1px solid rgba(245,158,11,0.2); }

        .p2-toggle {
          width: 42px; height: 24px;
          background: linear-gradient(135deg, #5b21b6, #7c3aed);
          border-radius: 12px; position: relative; cursor: pointer;
          box-shadow: 0 0 12px rgba(109,40,217,0.38); border: none;
          transition: opacity 0.2s;
        }

        .p2-toggle-off {
          background: rgba(255,255,255,0.08) !important;
          box-shadow: none !important;
        }

        .p2-toggle-pip {
          position: absolute; top: 3px; right: 3px;
          width: 18px; height: 18px; background: #fff; border-radius: 50%;
          transition: right 0.2s;
        }

        /* ── SIDEBAR WIDGETS ── */
        .p2-stat-row {
          display: flex; justify-content: space-between; align-items: center;
          padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.04);
        }

        .p2-stat-row:last-child { border-bottom: none; }
        .p2-stat-lbl { font-size: 12px; color: rgba(255,255,255,0.35); }
        .p2-stat-val { font-size: 12px; color: rgba(255,255,255,0.75); font-weight: 500; }

        .p2-insight {
          background: rgba(109,40,217,0.06);
          border: 1px solid rgba(109,40,217,0.15);
          border-radius: 12px; padding: 13px 14px;
          font-size: 12px; line-height: 1.55;
          color: rgba(255,255,255,0.55);
          margin-bottom: 10px;
          position: relative; overflow: hidden;
        }

        .p2-insight:last-child { margin-bottom: 0; }

        .p2-insight::before {
          content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 2px;
          background: linear-gradient(to bottom, #7c3aed, #4f46e5);
        }

        .p2-insight strong { color: rgba(255,255,255,0.8); font-weight: 500; }

        /* ── RESPONSIVE ── */
        @media (max-width: 1000px) {
          .p2-body { grid-template-columns: 1fr; padding: 24px 20px 40px; }
          .p2-identity { padding: 0 20px; }
          .p2-tabs-bar { padding: 24px 20px 0; overflow-x: auto; }
          .p2-score-pill { position: static; margin: 0 20px 20px; align-self: flex-start; }
          .p2-analytics-grid { grid-template-columns: repeat(2, 1fr); }
          .p2-info-grid { grid-template-columns: 1fr; }
        }

        @media (max-width: 600px) {
          .p2-hero-kpis { gap: 18px; }
          .p2-analytics-grid { grid-template-columns: 1fr; }
          .p2-name { font-size: 26px; }
        }

        /* ── SHIMMER ── */
        @keyframes p2Shimmer {
          0%   { background-position: -400px 0; }
          100% { background-position:  400px 0; }
        }
      `}</style>

      <div className="p2-root">
        <div className="p2-ambient" />

        {/* ── HERO ── */}
        <div className="p2-hero">
          <div className="p2-hero-grid" />
          <div className="p2-hero-glow-l" />
          <div className="p2-hero-glow-r" />
        </div>

        {/* ── SCORE PILL ── */}
        <div style={{ position: 'relative', zIndex: 2 }}>
          <div className="p2-score-pill" style={{ position: 'absolute', top: -220, right: 48 }}>
            <Zap size={16} style={{ color: '#a78bfa' }} />
            <div className="p2-score-num"><Counter to={87} /></div>
            <div className="p2-score-detail">
              <div className="p2-score-label">AI Score</div>
              <div className="p2-score-rank">Top 12%</div>
            </div>
          </div>
        </div>

        {/* ── IDENTITY ROW ── */}
        <div className="p2-identity">
          <div className="p2-avatar-frame">
            <div className="p2-avatar-ring" />
            <div className="p2-avatar">{initial}</div>
            <div className="p2-pulse" />
          </div>
          <div className="p2-id-info">
            <div className="p2-name">{user.full_name || 'Anonymous User'}</div>
            <div className="p2-title">AI Support Operations Specialist · Enterprise Team</div>
            <div className="p2-badges">
              <span className="p2-badge p2-badge-role">{user.role}</span>
              <span className="p2-badge p2-badge-status">● Online</span>
              <span className="p2-badge p2-badge-award">★ Top Performer</span>
            </div>
            <div className="p2-hero-kpis">
              <div className="p2-kpi">
                <div className="p2-kpi-num"><Counter to={214} /></div>
                <div className="p2-kpi-lbl">Resolved</div>
              </div>
              <div className="p2-kpi">
                <div className="p2-kpi-num"><Counter to={98} suffix="%" /></div>
                <div className="p2-kpi-lbl">Satisfaction</div>
              </div>
              <div className="p2-kpi">
                <div className="p2-kpi-num">4 min</div>
                <div className="p2-kpi-lbl">Avg Response</div>
              </div>
              <div className="p2-kpi">
                <div className="p2-kpi-num">Level 2</div>
                <div className="p2-kpi-lbl">Role Level</div>
              </div>
            </div>
          </div>
        </div>

        {/* ── TABS ── */}
        <div className="p2-tabs-bar">
          {(['overview', 'analytics', 'security'] as const).map(t => (
            <button
              key={t}
              className={`p2-tab ${activeTab === t ? 'p2-tab-active' : ''}`}
              onClick={() => setActiveTab(t)}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        {/* ── BODY ── */}
        <div className="p2-body">

          {/* ── MAIN ── */}
          <div className="p2-main">

            {/* AI Insight Banner */}
            <div className="p2-ai-banner">
              <div className="p2-ai-icon-wrap"><Bot size={17} /></div>
              <div className="p2-ai-text">
                <div className="p2-ai-label">AI Insight · Today</div>
                <div className="p2-ai-msg">
                  SLA compliance improved <strong>+18%</strong> this week. Predicted high-productivity session ahead —
                  infrastructure incident tickets align with your core expertise. Recommended: prioritize queue #4812–4819.
                </div>
              </div>
            </div>

            {/* OVERVIEW TAB */}
            {activeTab === 'overview' && (
              <>
                {/* General Info */}
                <div className="p2-card">
                  <div className="p2-card-hd">
                    <div className="p2-card-title">General Information</div>
                    <button className="p2-card-action"><Edit3 size={12} /> Edit</button>
                  </div>
                  <div className="p2-info-grid">
                    {[
                      { label: 'Full Name',    icon: <User     size={15} />, val: user.full_name || '—' },
                      { label: 'Email',        icon: <Mail     size={15} />, val: user.email           },
                      { label: 'Role Access',  icon: <Shield   size={15} />, val: user.role            },
                      { label: 'Joined',       icon: <Calendar size={15} />, val: joinedFull           },
                      { label: 'Location',     icon: <MapPin   size={15} />, val: 'Tunis, Tunisia'   },
                      { label: 'Languages',    icon: <Globe    size={15} />, val: 'EN · DE · FR'       },
                    ].map(f => (
                      <div key={f.label}>
                        <div className="p2-field-label">{f.label}</div>
                        <div className="p2-field-val">
                          <span className="p2-field-icon">{f.icon}</span>
                          <span className="p2-field-text">{f.val}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  <button className="p2-edit-btn"><Edit3 size={14} /> Edit Information</button>
                </div>

                {/* Skills */}
                <div className="p2-card">
                  <div className="p2-card-hd">
                    <div className="p2-card-title">Skills &amp; Expertise</div>
                    <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.28)' }}>AI-verified</span>
                  </div>
                  <div className="p2-skills-wrap">
                    {[
                      { name: 'AI / NLP',            color: '#7c3aed' },
                      { name: 'Infrastructure',       color: '#3b82f6' },
                      { name: 'Incident Management',  color: '#ef4444' },
                      { name: 'SLA Optimization',     color: '#10b981' },
                      { name: 'Ticket Routing',       color: '#f59e0b' },
                      { name: 'Customer Support',     color: '#06b6d4' },
                      { name: 'Security Awareness',   color: '#a855f7' },
                      { name: 'Data Analysis',        color: '#6366f1' },
                      { name: 'Workflow Design',      color: '#14b8a6' },
                    ].map(s => (
                      <div key={s.name} className="p2-skill">
                        <div className="p2-skill-dot" style={{ background: s.color, boxShadow: `0 0 6px ${s.color}80` }} />
                        {s.name}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Activity Timeline */}
                <div className="p2-card">
                  <div className="p2-card-hd">
                    <div className="p2-card-title">Activity Timeline</div>
                    <button className="p2-card-action">View all <ChevronRight size={12} /></button>
                  </div>
                  <div className="p2-tl">
                    <div className="p2-tl-spine" />
                    {[
                      { dot: 'purple', title: 'Resolved critical ticket #4812',   meta: '12 min ago'  },
                      { dot: 'green',  title: 'Received 5-star customer rating',  meta: '1 hr ago'    },
                      { dot: 'amber',  title: 'SLA alert — ticket #4805 escalated', meta: '2 hr ago'  },
                      { dot: 'blue',   title: 'Joined team standup (Q2 review)',   meta: 'Yesterday'   },
                      { dot: 'purple', title: 'AI recommendation accepted #4791', meta: '2 days ago'  },
                      { dot: 'green',  title: 'Security audit completed',          meta: '3 days ago'  },
                    ].map((item, i) => (
                      <div key={i} className="p2-tl-item">
                        <div className={`p2-tl-dot ${item.dot}`} />
                        <div className="p2-tl-title">{item.title}</div>
                        <div className="p2-tl-meta">{item.meta}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}

            {/* ANALYTICS TAB */}
            {activeTab === 'analytics' && (
              <>
                <div className="p2-analytics-grid">
                  {[
                    { icon: <BarChart2 size={15} />, cls: 'purple', val: 214,   suffix: '',   lbl: 'Tickets Resolved', pct: 87 },
                    { icon: <Clock     size={15} />, cls: 'green',  val: 4,     suffix: 'min', lbl: 'Avg Response',   pct: 94 },
                    { icon: <Star      size={15} />, cls: 'amber',  val: 98,    suffix: '%',  lbl: 'Satisfaction',    pct: 98 },
                    { icon: <Zap       size={15} />, cls: 'purple', val: 87,    suffix: '',   lbl: 'AI Score',         pct: 87 },
                    { icon: <TrendingUp size={15}/>, cls: 'blue',   val: 94,    suffix: '%',  lbl: 'SLA Compliance',  pct: 94 },
                    { icon: <Award     size={15} />, cls: 'green',  val: 78,    suffix: '%',  lbl: 'First Contact',   pct: 78 },
                  ].map((m, i) => (
                    <div key={i} className={`p2-metric-card ${m.cls}`}>
                      <div className={`p2-metric-icon ${m.cls}`}>{m.icon}</div>
                      <div className="p2-metric-val"><Counter to={m.val} suffix={m.suffix} /></div>
                      <div className="p2-metric-lbl">{m.lbl}</div>
                      <div className="p2-metric-bar">
                        <div className={`p2-metric-fill ${m.cls}`} style={{ width: `${m.pct}%` }} />
                      </div>
                    </div>
                  ))}
                </div>

                <div className="p2-card">
                  <div className="p2-card-hd">
                    <div className="p2-card-title">Performance Breakdown</div>
                  </div>
                  {[
                    { label: 'Resolution Speed',    pct: 87, color: 'linear-gradient(to right,#5b21b6,#7c3aed)' },
                    { label: 'SLA Compliance',      pct: 94, color: 'linear-gradient(to right,#065f46,#10b981)' },
                    { label: 'AI Efficiency',       pct: 81, color: 'linear-gradient(to right,#92400e,#f59e0b)' },
                    { label: 'Customer Sentiment',  pct: 96, color: 'linear-gradient(to right,#1d4ed8,#3b82f6)' },
                    { label: 'First Contact Resolve', pct: 78, color: 'linear-gradient(to right,#5b21b6,#7c3aed)' },
                    { label: 'Collaboration Score', pct: 91, color: 'linear-gradient(to right,#065f46,#10b981)' },
                  ].map(p => (
                    <div key={p.label} className="p2-perf-row">
                      <span className="p2-perf-lbl">{p.label}</span>
                      <div className="p2-perf-track">
                        <div className="p2-perf-bar" style={{ width: `${p.pct}%`, background: p.color }} />
                      </div>
                      <span className="p2-perf-pct">{p.pct}%</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* SECURITY TAB */}
            {activeTab === 'security' && (
              <>
                <div className="p2-card">
                  <div className="p2-card-hd">
                    <div className="p2-card-title">Security Center</div>
                  </div>

                  {/* Score Ring */}
                  <div className="p2-sec-score">
                    <div className="p2-sec-ring">
                      <svg width="62" height="62" viewBox="0 0 62 62">
                        <circle cx="31" cy="31" r="27" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="5" />
                        <circle cx="31" cy="31" r="27" fill="none" stroke="#10b981" strokeWidth="5"
                          strokeDasharray={`${2 * Math.PI * 27 * 0.94} ${2 * Math.PI * 27}`}
                          strokeLinecap="round" />
                      </svg>
                      <div className="p2-sec-ring-num">94</div>
                    </div>
                    <div className="p2-sec-info">
                      <div className="p2-sec-name">Security Score — Excellent</div>
                      <div className="p2-sec-desc">Last login detected from Tunis, TN · May 8, 2026</div>
                    </div>
                  </div>

                  {/* Security Items */}
                  {[
                    { icon: <Key       size={15} />, cls: 'amber',  label: 'Two-Factor Authentication', sub: 'Authenticator app active',  badge: 'on',   badgeText: 'Enabled'  },
                    { icon: <Lock      size={15} />, cls: 'purple', label: 'Password Strength',         sub: 'Last changed 14 days ago',  badge: 'on',   badgeText: 'Strong'   },
                    { icon: <Smartphone size={15}/>, cls: 'green',  label: 'Trusted Devices',           sub: '2 devices registered',      badge: 'on',   badgeText: '2 Active' },
                    { icon: <Eye       size={15} />, cls: 'blue',   label: 'Login History',             sub: '5 recent sessions visible', badge: 'off',  badgeText: 'View'     },
                    { icon: <Bell      size={15} />, cls: 'purple', label: 'Security Alerts',           sub: 'Suspicious login detection', badge: 'on',  badgeText: 'On'       },
                    { icon: <AlertTriangle size={15}/>, cls: 'amber', label: 'Phishing Shield',         sub: 'AI-powered threat analysis', badge: 'on',  badgeText: 'Active'   },
                  ].map(s => (
                    <div key={s.label} className="p2-sec-row">
                      <div className="p2-sec-left">
                        <div className={`p2-sec-icon ${s.cls}`}>{s.icon}</div>
                        <div>
                          <div className="p2-sec-label">{s.label}</div>
                          <div className="p2-sec-sub">{s.sub}</div>
                        </div>
                      </div>
                      <span className={`p2-sec-badge ${s.badge}`}>{s.badgeText}</span>
                    </div>
                  ))}
                </div>

                {/* Preferences */}
                <div className="p2-card">
                  <div className="p2-card-hd">
                    <div className="p2-card-title">Preferences</div>
                  </div>
                  {[
                    { icon: <Bell size={15} />, cls: 'purple', label: 'Email Notifications', sub: 'Daily digest & ticket alerts', on: true  },
                    { icon: <Bot  size={15} />, cls: 'blue',   label: 'AI Recommendations',  sub: 'Smart routing & suggestions',  on: true  },
                    { icon: <Activity size={15} />, cls: 'green', label: 'Usage Analytics', sub: 'Share anonymised metrics',      on: false },
                  ].map(p => (
                    <div key={p.label} className="p2-sec-row">
                      <div className="p2-sec-left">
                        <div className={`p2-sec-icon ${p.cls}`}>{p.icon}</div>
                        <div>
                          <div className="p2-sec-label">{p.label}</div>
                          <div className="p2-sec-sub">{p.sub}</div>
                        </div>
                      </div>
                      <button className={`p2-toggle ${p.on ? '' : 'p2-toggle-off'}`}>
                        <div className="p2-toggle-pip" style={{ right: p.on ? 3 : undefined, left: p.on ? undefined : 3 }} />
                      </button>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* ── SIDEBAR ── */}
          <div className="p2-side">

            {/* Account Card */}
            <div className="p2-card">
              <div className="p2-card-title" style={{ marginBottom: 16 }}>Account</div>
              <div className="p2-stat-row"><span className="p2-stat-lbl">Member since</span><span className="p2-stat-val">{memberSince}</span></div>
              <div className="p2-stat-row"><span className="p2-stat-lbl">Role level</span><span className="p2-stat-val">Level 2</span></div>
              <div className="p2-stat-row"><span className="p2-stat-lbl">Team</span><span className="p2-stat-val">Enterprise</span></div>
              <div className="p2-stat-row"><span className="p2-stat-lbl">Tickets today</span><span className="p2-stat-val">12</span></div>
              <div className="p2-stat-row"><span className="p2-stat-lbl">Queue status</span><span className="p2-stat-val" style={{ color: '#34d399' }}>● Live</span></div>
              <div className="p2-stat-row"><span className="p2-stat-lbl">AI mode</span><span className="p2-stat-val" style={{ color: '#a78bfa' }}>⚡ Assisted</span></div>
            </div>

            {/* AI Insights */}
            <div className="p2-card">
              <div className="p2-card-hd">
                <div className="p2-card-title">AI Insights</div>
                <Cpu size={14} style={{ color: '#7c3aed' }} />
              </div>
              <div className="p2-insight">
                <strong>High productivity predicted</strong> for the next 3 hours based on your rhythm patterns.
              </div>
              <div className="p2-insight">
                <strong>SLA rate improved +18%</strong> — your infrastructure expertise is above team average.
              </div>
              <div className="p2-insight">
                Recommended learning: <strong>AI Triage v2 module</strong> — estimated 23 min.
              </div>
              <div className="p2-insight">
                <strong>Burnout risk: Low.</strong> Healthy workload balance detected this week.
              </div>
            </div>

            {/* Security Score */}
            <div className="p2-card">
              <div className="p2-card-title" style={{ marginBottom: 16 }}>Security at a Glance</div>
              <div className="p2-stat-row"><span className="p2-stat-lbl">Security score</span><span className="p2-stat-val" style={{ color: '#6ee7b7' }}>94 / 100</span></div>
              <div className="p2-stat-row"><span className="p2-stat-lbl">2FA status</span><span className="p2-stat-val" style={{ color: '#6ee7b7' }}>✓ Enabled</span></div>
              <div className="p2-stat-row"><span className="p2-stat-lbl">Last login</span><span className="p2-stat-val">Tunis, TN</span></div>
              <div className="p2-stat-row"><span className="p2-stat-lbl">Active sessions</span><span className="p2-stat-val">2</span></div>
              <div className="p2-stat-row"><span className="p2-stat-lbl">Threats blocked</span><span className="p2-stat-val" style={{ color: '#a78bfa' }}>0</span></div>
            </div>

          </div>
        </div>
      </div>
    </>
  );
};

export default Profile;