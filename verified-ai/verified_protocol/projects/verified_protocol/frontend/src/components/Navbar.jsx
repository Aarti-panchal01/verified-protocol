import { NavLink } from 'react-router-dom';

export default function Navbar() {
    return (
        <nav className="navbar">
            <NavLink to="/" className="navbar-brand">
                <span className="navbar-brand-icon">⬡</span>
                Verified Protocol
            </NavLink>

            <ul className="navbar-links">
                <li><NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>Submit</NavLink></li>
                <li><NavLink to="/dashboard" className={({ isActive }) => isActive ? 'active' : ''}>Dashboard</NavLink></li>
                <li><NavLink to="/verifier" className={({ isActive }) => isActive ? 'active' : ''}>Verifier</NavLink></li>
                <li><NavLink to="/explorer" className={({ isActive }) => isActive ? 'active' : ''}>Explorer</NavLink></li>
            </ul>

            <span className="navbar-badge">Testnet</span>
        </nav>
    );
}
