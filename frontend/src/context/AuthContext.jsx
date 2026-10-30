import React, { createContext, useCallback, useEffect, useState } from 'react';
import axiosInstance, { refreshAccessToken, setSessionExpiredHandler, tokenStore } from '../api/axios';

export const AuthContext = createContext(null);

const LOGIN_PATH = `${import.meta.env.BASE_URL}#/login`;

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    const endSession = useCallback(() => {
        tokenStore.clear();
        setUser(null);
        window.location.href = LOGIN_PATH;
    }, []);

    useEffect(() => {
        setSessionExpiredHandler(endSession);
        // The access token is memory-only, so on load exchange the httpOnly
        // refresh cookie for a new one. No cookie (or an expired one) just
        // means "not signed in".
        const restore = async () => {
            try {
                await refreshAccessToken();
                const response = await axiosInstance.get('/auth/me/');
                setUser(response.data);
            } catch {
                tokenStore.clear();
            } finally {
                setLoading(false);
            }
        };
        restore();
    }, [endSession]);

    const login = async (email, password) => {
        const response = await axiosInstance.post('/auth/login/', { email, password });
        const { access, user: userData } = response.data;
        tokenStore.set(access);
        setUser(userData);
        return userData;
    };

    const logout = async () => {
        try {
            await axiosInstance.post('/auth/logout/', {});
        } catch {
            // The local session ends regardless.
        }
        endSession();
    };

    const value = {
        user,
        loading,
        login,
        logout,
        isAuthenticated: !!user,
        isSuperAdmin: user?.role === 'SUPER_ADMIN',
        isManager: ['SUPER_ADMIN', 'MANAGER'].includes(user?.role),
        isLoanOfficer: ['SUPER_ADMIN', 'MANAGER', 'LOAN_OFFICER'].includes(user?.role),
        // Matches FINANCE_STAFF on the server (approvals, ledger, dues).
        isFinance: ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT'].includes(user?.role),
    };

    return (
        <AuthContext.Provider value={value}>
            {!loading && children}
        </AuthContext.Provider>
    );
};
