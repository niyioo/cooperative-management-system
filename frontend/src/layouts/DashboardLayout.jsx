import React, { useState } from 'react'; // ✅ Added useState
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Navbar from '../components/Navbar';

const DashboardLayout = () => {
    // ✅ 1. Create the state to track if the menu is open
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);

    // ✅ 2. Helper functions to open and close
    const openSidebar = () => setIsSidebarOpen(true);
    const closeSidebar = () => setIsSidebarOpen(false);

    return (
        <div className="flex h-screen overflow-hidden bg-slate-50">
            {/* ✅ 3. Pass props to Sidebar */}
            <Sidebar 
                isOpen={isSidebarOpen} 
                toggleSidebar={closeSidebar} 
            />
            
            <div className="flex flex-col flex-1 w-0 overflow-hidden">
                {/* ✅ 4. Pass the open function to the Navbar */}
                <Navbar onMenuClick={openSidebar} />
                
                <main className="flex-1 relative z-0 overflow-y-auto focus:outline-none p-4 sm:p-6 lg:p-8">
                    {/* Render the matched child route component */}
                    <Outlet />
                </main>
            </div>
        </div>
    );
};

export default DashboardLayout;