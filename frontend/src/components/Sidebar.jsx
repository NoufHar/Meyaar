import {
  Home,
  Plus,
  Map,
  FileText,
  BookOpen,
  Settings,
  LogOut,
} from "lucide-react";

const items=[
  ["home","Home",Home],
  ["inspection","New Inspection",Plus],
  ["workspace","Workspace",Map],
  ["reports","Reports",FileText],
];

export default function Sidebar({page,setPage,user,onLogout}){
  return (
    <aside className="sidebar">
      <div className="brand">
        <img src="/branding/meyaar-logo.png"/>
      </div>

      <nav>
        {items.map(([id,label,Icon])=>(
          <button
            key={id}
            className={page===id?"nav-item active":"nav-item"}
            onClick={()=>setPage(id)}
          >
            <Icon size={18}/>
            {label}
          </button>
        ))}

        <button className="nav-item">
          <BookOpen size={18}/>
          Knowledge (GeoSA)
        </button>
      </nav>

      <div className="sidebar-bottom">
        <button className="nav-item">
          <Settings size={18}/>
          Settings
        </button>

        <div className="profile">
          <div className="avatar">
            {user?.name?.[0]?.toUpperCase()||"U"}
          </div>
          <div>
            <strong>{user?.name||"Meyaar User"}</strong>
            <span>{user?.email}</span>
          </div>
        </div>

        <button className="logout" onClick={onLogout}>
          <LogOut size={17}/>
          Logout
        </button>
      </div>
    </aside>
  );
}