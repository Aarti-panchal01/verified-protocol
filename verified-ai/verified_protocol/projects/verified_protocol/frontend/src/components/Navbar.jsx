import { NavLink } from 'react-router-dom'

export default function Navbar() {
    return (
        <nav className="navbar">
            <div className="navbar-inner">
                <NavLink to="/" className="navbar-brand">
                    <span className="brand-icon">🛡️</span>
                    <span>Verified Protocol</span>
                </NavLink>

                <ul className="navbar-links">
                    <li>
                        <NavLink to="/" className={({ isActive }) => isActive ? 'active' : ''} end>
                            Submit
                        </NavLink>
                    </li>
                    <li>
                        <NavLink to="/records" className={({ isActive }) => isActive ? 'active' : ''}>
                            Records
                        </NavLink>
                    </li>
                    <li>
                        <NavLink to="/verify" className={({ isActive }) => isActive ? 'active' : ''}>
                            Verifier
                        </NavLink>
                    </li>
                </ul>

                <div className="navbar-badge">
                    <span className="dot" />
                    Testnet
                </div>
            </div>
        </nav>
    )
}
