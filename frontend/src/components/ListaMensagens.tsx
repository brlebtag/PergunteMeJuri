import { useEffect, useRef } from "react"
import { Scale, User } from "lucide-react"
import Markdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { cn } from "@/lib/utils"
import type { Mensagem } from "@/tipos"

interface Props {
  mensagens: Mensagem[]
  aguardando: boolean
}

function Balao({ mensagem }: { mensagem: Mensagem }) {
  const daIA = mensagem.autor === "juri"

  return (
    <div className={cn("flex gap-3", !daIA && "flex-row-reverse")}>
      <div
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-full",
          daIA ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
        )}
        aria-hidden
      >
        {daIA ? <Scale className="size-4" /> : <User className="size-4" />}
      </div>

      <div
        className={cn(
          "max-w-[75%] rounded-lg px-4 py-2.5 text-sm",
          daIA ? "bg-muted" : "bg-primary text-primary-foreground whitespace-pre-wrap",
        )}
      >
        <span className="sr-only">{daIA ? "Juri respondeu:" : "Você perguntou:"}</span>
        {daIA ? (
          // A pergunta do usuario vai como texto puro de proposito: renderizar
          // markdown do que ele digitou nao agrega e abriria espaco para
          // formatacao acidental.
          <div
            className={cn(
              "prose prose-sm dark:prose-invert max-w-none",
              "prose-headings:mt-4 prose-headings:mb-2 prose-headings:text-sm",
              "prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5",
              "prose-pre:bg-background prose-pre:text-foreground",
              "first:prose-headings:mt-0",
            )}
          >
            <Markdown remarkPlugins={[remarkGfm]}>{mensagem.texto}</Markdown>
          </div>
        ) : (
          mensagem.texto
        )}
      </div>
    </div>
  )
}

export function ListaMensagens({ mensagens, aguardando }: Props) {
  const fim = useRef<HTMLDivElement>(null)

  // Acompanha a resposta enquanto ela e gerada token a token.
  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
  }, [mensagens, aguardando])

  if (mensagens.length === 0) {
    return (
      <div className="text-muted-foreground flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
        <Scale className="size-8" aria-hidden />
        <p className="text-sm">Faça uma pergunta sobre a legislação brasileira.</p>
        <p className="text-xs">As respostas usam apenas os trechos de lei recuperados.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5 px-4 py-6">
      {mensagens.map((mensagem) => (
        <Balao key={mensagem.id} mensagem={mensagem} />
      ))}

      {aguardando && (
        <div className="text-muted-foreground flex items-center gap-2 pl-11 text-sm">
          <span className="bg-muted-foreground size-1.5 animate-bounce rounded-full [animation-delay:-0.3s]" />
          <span className="bg-muted-foreground size-1.5 animate-bounce rounded-full [animation-delay:-0.15s]" />
          <span className="bg-muted-foreground size-1.5 animate-bounce rounded-full" />
          <span className="ml-1 text-xs">consultando as leis…</span>
        </div>
      )}

      <div ref={fim} />
    </div>
  )
}
