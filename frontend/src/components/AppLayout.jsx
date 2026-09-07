import Sidebar from "./Sidebar";
import ChatPopup from "./ChatPopup";

export default function AppLayout({
  children,
  page,
  setPage,
  user,
  analysis,
  onLogout,
}){
  return (
    <div className="app-shell">
      <Sidebar
        page={page}
        setPage={setPage}
        user={user}
        onLogout={onLogout}
      />

      <main className="app-main">{children}</main>

      <ChatPopup analysis={analysis}/>
    </div>
  );
}