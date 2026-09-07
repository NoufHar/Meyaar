import {useState} from "react";
import {Bot,MessageCircle,Send,X} from "lucide-react";
import {api} from "../api";

export default function ChatPopup({analysis}){
  const [open,setOpen]=useState(false);
  const [message,setMessage]=useState("");
  const [messages,setMessages]=useState([]);
  const [loading,setLoading]=useState(false);

  function localAnswer(question){
    if(!analysis) return "Run an inspection first.";

    const findings=analysis.findings||[];
    const q=question.toLowerCase();

    if(q.includes("كم")||q.includes("how many")){
      return `The current inspection contains ${findings.length} findings.`;
    }

    if(q.includes("high")||q.includes("عالي")||q.includes("حرج")){
      const count=findings.filter(
        x=>["high","critical"].includes(x.severity?.toLowerCase())
      ).length;

      return `There are ${count} high-priority findings.`;
    }

    if(q.includes("summary")||q.includes("لخص")||q.includes("ملخص")){
      return `${analysis.filename} has ${findings.length} findings. ${
        findings.slice(0,3).map(x=>x.error_type).join(", ")||"No findings reported."
      }`;
    }

    const types=[...new Set(findings.map(x=>x.error_type).filter(Boolean))];

    return types.length
      ? `Detected finding types: ${types.join(", ")}.`
      : "No findings were reported for this inspection.";
  }

  async function ask(text=message){
    const question=text.trim();
    if(!question) return;

    setMessages(prev=>[...prev,{role:"user",text:question}]);
    setMessage("");
    setLoading(true);

    let answer;

    try{
      if(analysis?.input_type==="vector"&&analysis?.run_id){
        const {data}=await api.post(
          `/api/validation/${analysis.run_id}/chat`,
          {question}
        );

        answer=data.answer;
      }else{
        answer=localAnswer(question);
      }
    }catch{
      answer=localAnswer(question);
    }

    setMessages(prev=>[...prev,{role:"assistant",text:answer}]);
    setLoading(false);
  }

  return (
    <>
      <button className="chat-fab" onClick={()=>setOpen(!open)}>
        <MessageCircle/>
      </button>

      {open&&(
        <aside className="chat-popup">
          <header>
            <div>
              <Bot size={20}/>
              <div>
                <strong>Meyaar Assistant</strong>
                <span>● Online</span>
              </div>
            </div>

            <button onClick={()=>setOpen(false)}>
              <X size={18}/>
            </button>
          </header>

          <div className="chat-body">
            {!messages.length&&(
              <>
                <div className="assistant-message">
                  Ask me about the current inspection.
                </div>

                {[
                  "Summarize this inspection",
                  "How many findings were detected?",
                  "What are the highest severity issues?",
                ].map(text=>(
                  <button key={text} onClick={()=>ask(text)}>
                    {text}
                  </button>
                ))}
              </>
            )}

            {messages.map((item,index)=>(
              <div
                key={index}
                className={`chat-message ${item.role}`}
              >
                {item.text}
              </div>
            ))}

            {loading&&(
              <div className="chat-message assistant">Thinking...</div>
            )}
          </div>

          <form
            className="chat-input"
            onSubmit={e=>{
              e.preventDefault();
              ask();
            }}
          >
            <input
              value={message}
              onChange={e=>setMessage(e.target.value)}
              placeholder="Ask Meyaar anything..."
            />

            <button type="submit">
              <Send size={17}/>
            </button>
          </form>
        </aside>
      )}
    </>
  );
}