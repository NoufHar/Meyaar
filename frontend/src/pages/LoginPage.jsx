import {useState} from "react";
import {api,setToken} from "../api";

export default function LoginPage({onLogin,onRegister}){
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [loading,setLoading]=useState(false);

  async function submit(e){
    e.preventDefault();

    try{
      setLoading(true);

      const {data}=await api.post("/auth/login",{email,password});
      const token=data.access_token||data.token;

      localStorage.setItem("meyaar_token",token);
      setToken(token);

      const me=await api.get("/auth/me");
      onLogin(me.data);
    }catch(error){
      alert(error.response?.data?.detail||"Login failed.");
    }finally{
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <img src="/branding/meyaar-logo.png" className="auth-logo"/>

        <h1>Welcome Back</h1>
        <p>Sign in to continue to Meyaar</p>

        <input
          placeholder="Email address"
          value={email}
          onChange={e=>setEmail(e.target.value)}
        />

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={e=>setPassword(e.target.value)}
        />

        <button className="button primary" disabled={loading}>
          {loading?"Signing in...":"Sign In"}
        </button>

        <span className="auth-switch">
          Don't have an account?
          <button type="button" onClick={onRegister}>Create account</button>
        </span>
      </form>
    </div>
  );
}