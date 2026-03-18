import { useState, useEffect } from 'react';
import axiosInstance from '../api/axios';

export const useNotifications = () => {
    const [notifications, setNotifications] = useState([]);
    const [unreadCount, setUnreadCount] = useState(0);

    const fetchData = async () => {
        try {
            // 1. Get the actual list for the dropdown
            const listRes = await axiosInstance.get('/notifications/latest/');
            // 2. Get the count for the red dot
            const countRes = await axiosInstance.get('/notifications/unread_count/');
            
            setNotifications(listRes.data);
            setUnreadCount(countRes.data.unread_count);
        } catch (error) {
            console.error("Notification Error:", error);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000); // Check every 30s
        return () => clearInterval(interval);
    }, []);

    return { notifications, unreadCount, refresh: fetchData };
};