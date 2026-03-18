import React, { createContext, useState, useEffect } from 'react';
import axiosInstance from '../api/axios';

export const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const checkAuth = async () => {
            const token = localStorage.getItem('accessToken');
            if (token) {
                try {
                    // Fetch fresh user profile on load
                    const response = await axiosInstance.get('/auth/me/');
                    setUser(response.data);
                } catch (error) {
                    console.error("Failed to restore session:", error);
                    logout();
                }
            }
            setLoading(false);
        };
        checkAuth();
    }, []);

    const login = async (email, password) => {
        const response = await axiosInstance.post('/auth/login/', { email, password });
        const { access, refresh, user: userData } = response.data;
        
        localStorage.setItem('accessToken', access);
        localStorage.setItem('refreshToken', refresh);
        setUser(userData);
        return userData;
    };

    const logout = () => {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        setUser(null);
        window.location.href = `${import.meta.env.BASE_URL}login`;
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
    };

    return (
        <AuthContext.Provider value={value}>
            {!loading && children}
        </AuthContext.Provider>
    );
};