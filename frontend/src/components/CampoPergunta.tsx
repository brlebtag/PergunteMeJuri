import { useState, type FormEvent } from "react"
import { SendHorizontal } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

interface Props {
  onEnviar: (pergunta: string) => void
  desabilitado: boolean
}

export function CampoPergunta({ onEnviar, desabilitado }: Props) {
  const [texto, setTexto] = useState("")

  function enviar(evento: FormEvent) {
    evento.preventDefault()
    const pergunta = texto.trim()
    if (!pergunta || desabilitado) return

    onEnviar(pergunta)
    setTexto("")
  }

  return (
    <form onSubmit={enviar} className="flex items-center gap-2 border-t px-4 py-3">
      <Input
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        placeholder="Pergunte sobre uma lei…"
        aria-label="Sua pergunta"
        disabled={desabilitado}
      />
      <Button type="submit" size="icon" disabled={desabilitado || !texto.trim()}>
        <SendHorizontal className="size-4" />
        <span className="sr-only">Enviar</span>
      </Button>
    </form>
  )
}
