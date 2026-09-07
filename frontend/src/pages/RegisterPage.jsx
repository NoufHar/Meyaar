import {useState} from "react";
import {api} from "../api";

export default function RegisterPage({onCreated,onLogin}){
  const [form,setForm]=useState({
    name:"",
    email:"",
    password:"",
    confirm:"",
  });

  function update(e){
    setForm({...form,[e.target.name]:e.target.value});
  }

  async function submit(e){
    e.preventDefault();

    if(form.password!==form.confirm){
      alert("Passwords do not match.");
      return;
    }

    try{
      await api.post("/auth/register",{
        name:form.name,
        email:form.email,
        password:form.password,
      });

      onCreated();
    }catch(error){
      alert(error.response?.data?.detail||"Could not create account.");
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <img src="/branding/meyaar-logo.png" className="auth-logo"/>

        <h1>Create Your Account</h1>
        <p>Join Meyaar and start inspecting your geospatial data.</p>

        <input name="name" placeholder="Full name" onChange={update}/>
        <input name="email" placeholder="Email address" onChange={update}/>
        <input name="password" type="password" placeholder="Password" onChange={update}/>
        <input name="confirm" type="password" placeholder="Confirm password" onChange={update}/>

        <button className="button primary">Create Account</button>

        <span className="auth-switch">
          Already have an account?
          <button type="button" onClick={onLogin}>Sign in</button>
        </span>
      </form>
    </div>
  );
}