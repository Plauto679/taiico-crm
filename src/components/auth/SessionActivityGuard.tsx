'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';

const IDLE_TIMEOUT_MS = 60 * 60 * 1000;
const HEARTBEAT_MS = 5 * 60 * 1000;
const CHECK_INTERVAL_MS = 30 * 1000;
const LAST_ACTIVITY_KEY = 'taiico_last_activity';

export function SessionActivityGuard() {
    const pathname = usePathname();
    const router = useRouter();

    useEffect(() => {
        if (pathname === '/login') return;

        let lastHeartbeat = 0;
        let lastRecordedActivity = 0;
        let loggingOut = false;

        const readLastActivity = () => {
            const stored = Number(window.localStorage.getItem(LAST_ACTIVITY_KEY));
            return Number.isFinite(stored) && stored > 0 ? stored : Date.now();
        };

        const recordActivity = () => {
            const now = Date.now();
            if (now - lastRecordedActivity < 10_000) return;
            lastRecordedActivity = now;
            window.localStorage.setItem(LAST_ACTIVITY_KEY, String(now));
        };

        const finishLogout = () => {
            window.localStorage.removeItem(LAST_ACTIVITY_KEY);
            router.replace('/login');
            router.refresh();
        };

        const logout = async () => {
            if (loggingOut) return;
            loggingOut = true;
            try {
                await fetch('/api/logout', {
                    method: 'POST',
                    credentials: 'same-origin',
                    cache: 'no-store',
                });
            } finally {
                finishLogout();
            }
        };

        const refreshSession = async () => {
            const response = await fetch('/api/session/refresh', {
                method: 'POST',
                credentials: 'same-origin',
                cache: 'no-store',
            });
            if (response.status === 401) {
                await logout();
                return;
            }
            if (response.ok) lastHeartbeat = Date.now();
        };

        const checkSession = () => {
            const now = Date.now();
            const lastActivity = readLastActivity();
            if (now - lastActivity >= IDLE_TIMEOUT_MS) {
                void logout();
                return;
            }
            if (now - lastActivity < HEARTBEAT_MS && now - lastHeartbeat >= HEARTBEAT_MS) {
                void refreshSession();
            }
        };

        recordActivity();
        void refreshSession();

        const activityEvents: Array<keyof WindowEventMap> = [
            'pointerdown',
            'keydown',
            'scroll',
            'touchstart',
            'focus',
        ];
        activityEvents.forEach((eventName) => {
            window.addEventListener(eventName, recordActivity, { passive: true });
        });
        const interval = window.setInterval(checkSession, CHECK_INTERVAL_MS);

        return () => {
            window.clearInterval(interval);
            activityEvents.forEach((eventName) => {
                window.removeEventListener(eventName, recordActivity);
            });
        };
    }, [pathname, router]);

    return null;
}
