import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { Cabecalho } from "@/components/Cabecalho"
import { CampoPergunta } from "@/components/CampoPergunta"
import { DialogoLeis } from "@/components/DialogoLeis"
import { ListaMensagens } from "@/components/ListaMensagens"
import { Toaster } from "@/components/ui/sonner"
import { buscarConversa, perguntar } from "@/lib/api"
import { carregarSessao, limparSessao, salvarSessao } from "@/lib/sessao"
import type { Mensagem } from "@/tipos"

export default function App() {
  const [mensagens, setMensagens] = useState<Mensagem[]>([])
  const [threadId, setThreadId] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [leisAbertas, setLeisAbertas] = useState(false)
  const requisicao = useRef<AbortController | null>(null)

  // Restaura a sessao e a confere com o servidor: o thread_id guardado aqui
  // pode nao existir mais la (banco recriado, historico apagado).
  useEffect(() => {
    const sessao = carregarSessao()
    if (!sessao.threadId) return

    setThreadId(sessao.threadId)
    setMensagens(sessao.mensagens)

    buscarConversa(sessao.threadId)
      .then((doServidor) => {
        if (doServidor === null) {
          limparSessao()
          setThreadId(null)
          setMensagens([])
          return
        }
        setMensagens(doServidor)
      })
      .catch(() => {
        // API fora do ar: seguimos com o que estava salvo no navegador.
      })
  }, [])

  useEffect(() => {
    salvarSessao({ threadId, mensagens })
  }, [threadId, mensagens])

  const novaSessao = useCallback(() => {
    requisicao.current?.abort()
    requisicao.current = null

    limparSessao()
    setMensagens([])
    setThreadId(null)
    setEnviando(false)
    toast.success("Sessão encerrada.", {
      description: "O histórico deste navegador foi apagado.",
    })
  }, [])

  async function enviar(pergunta: string) {
    const idResposta = crypto.randomUUID()
    setMensagens((atuais) => [
      ...atuais,
      { id: crypto.randomUUID(), autor: "usuario", texto: pergunta },
      { id: idResposta, autor: "juri", texto: "" },
    ])
    setEnviando(true)

    const controlador = new AbortController()
    requisicao.current = controlador

    const acrescentar = (texto: string) =>
      setMensagens((atuais) =>
        atuais.map((m) => (m.id === idResposta ? { ...m, texto: m.texto + texto } : m)),
      )

    const descartarResposta = () =>
      setMensagens((atuais) => atuais.filter((m) => m.id !== idResposta))

    try {
      await perguntar(
        pergunta,
        threadId,
        {
          onInicio: setThreadId,
          onToken: acrescentar,
          onErro: (detalhe) => {
            descartarResposta()
            toast.error("O Juri não conseguiu responder.", { description: detalhe })
          },
        },
        controlador.signal,
      )
    } catch (erro) {
      // Abortar faz parte do fluxo de "nova sessão": nao e falha.
      if (!controlador.signal.aborted) {
        descartarResposta()
        toast.error("Falha ao falar com a API.", {
          description: erro instanceof Error ? erro.message : String(erro),
        })
      }
    } finally {
      if (requisicao.current === controlador) requisicao.current = null
      setEnviando(false)
    }
  }

  // Enquanto nenhum token chegou, o balao da resposta esta vazio: mostramos o
  // indicador de "digitando" no lugar dele.
  const aguardandoPrimeiroToken =
    enviando && mensagens.at(-1)?.autor === "juri" && mensagens.at(-1)?.texto === ""

  return (
    <div className="bg-background flex h-screen flex-col overflow-hidden">
      <Cabecalho
        threadId={threadId}
        onNovaSessao={novaSessao}
        onVerLeis={() => setLeisAbertas(true)}
      />

      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto h-full w-full max-w-3xl">
          <ListaMensagens
            mensagens={aguardandoPrimeiroToken ? mensagens.slice(0, -1) : mensagens}
            aguardando={aguardandoPrimeiroToken}
          />
        </div>
      </main>

      <div className="mx-auto w-full max-w-3xl">
        <CampoPergunta onEnviar={enviar} desabilitado={enviando} />
      </div>

      <DialogoLeis aberto={leisAbertas} onFechar={setLeisAbertas} />

      <Toaster />
    </div>
  )
}
