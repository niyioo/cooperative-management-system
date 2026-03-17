import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Navbar from '../components/Navbar';

const DashboardLayout = () => {
    return (
        <div className="flex h-screen overflow-hidden bg-slate-50">
            <Sidebar />
            
            <div className="flex flex-col flex-1 w-0 overflow-hidden">
                <Navbar />
                
                <main className="flex-1 relative z-0 overflow-y-auto focus:outline-none p-4 sm:p-6 lg:p-8">
                    {/* Render the matched child route component */}
                    <Outlet />
                </main>
            </div>
        </div>
    );
};

export default DashboardLayout;