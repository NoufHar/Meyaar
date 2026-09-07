import {useEffect,useState} from "react";
import {api,setToken} from "./api";
import AppLayout from "./components/AppLayout";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import HomePage from "./pages/HomePage";
import NewInspectionPage from "./pages/NewInspectionPage";
import WorkspacePage from "./pages/WorkspacePage";
import ReportsPage from "./pages/ReportsPage";

export default function App(){
  const [page,setPage]=useState("landing");
  const [user,setUser]=useState(null);
  const [analysis,setAnalysis]=useState(null);
  const [ready,setReady]=useState(false);

  useEffect(()=>{
    const token=localStorage.getItem("meyaar_token");
    if(!token){
      setReady(true);
      return;
    }

    setToken(token);
    api.get("/auth/me")
      .then(({data})=>{
        setUser(data);
        setPage("home");
      })
      .catch(()=>{
        localStorage.removeItem("meyaar_token");
        setToken(null);
      })
      .finally(()=>setReady(true));
  },[]);

  function login(userData){
    setUser(userData);
    setPage("home");
  }

  function logout(){
    localStorage.removeItem("meyaar_token");
    setToken(null);
    setUser(null);
    setAnalysis(null);
    setPage("landing");
  }

  async function openAnalysis(id){
    const {data}=await api.get(`/analyses/${id}`);
    setAnalysis(data);
    setPage("workspace");
  }

  if(!ready) return null;

  if(!user){
    if(page==="login"){
      return <LoginPage onLogin={login} onRegister={()=>setPage("register")}/>;
    }

    if(page==="register"){
      return (
        <RegisterPage
          onCreated={()=>setPage("login")}
          onLogin={()=>setPage("login")}
        />
      );
    }

    return <LandingPage onStart={()=>setPage("login")}/>;
  }

  return (
    <AppLayout
      page={page}
      setPage={setPage}
      user={user}
      analysis={analysis}
      onLogout={logout}
    >
      {page==="home"&&(
        <HomePage
          user={user}
          setPage={setPage}
          onOpen={openAnalysis}
        />
      )}

      {page==="inspection"&&(
        <NewInspectionPage
          onComplete={result=>{
            setAnalysis(result);
            setPage("workspace");
          }}
        />
      )}

      {page==="workspace"&&(
        <WorkspacePage
          analysis={analysis}
          setPage={setPage}
        />
      )}

      {page==="reports"&&(
        <ReportsPage analysis={analysis}/>
      )}
    </AppLayout>
  );
}