import { useEffect, useState } from "react"
import { BookText } from "lucide-react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { listarLeis } from "@/lib/api"

interface Props {
  aberto: boolean
  onFechar: (aberto: boolean) => void
}

export function DialogoLeis({ aberto, onFechar }: Props) {
  const [leis, setLeis] = useState<string[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  // Busca a cada abertura: a base pode ganhar leis novas enquanto a aba fica
  // aberta, e a chamada e barata.
  useEffect(() => {
    if (!aberto) return

    setLeis(null)
    setErro(null)
    listarLeis()
      .then(setLeis)
      .catch((e) => setErro(e instanceof Error ? e.message : String(e)))
  }, [aberto])

  return (
    <Dialog open={aberto} onOpenChange={onFechar}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Leis disponíveis</DialogTitle>
          <DialogDescription>
            O Juri responde usando apenas trechos destes documentos.
          </DialogDescription>
        </DialogHeader>

        {erro && (
          <p className="text-destructive text-sm">
            Não foi possível carregar a lista: {erro}
          </p>
        )}

        {!erro && leis === null && (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-4/5" />
          </div>
        )}

        {!erro && leis?.length === 0 && (
          <p className="text-muted-foreground text-sm">
            Nenhuma lei indexada ainda. Rode o <code>precompute_pipeline</code>.
          </p>
        )}

        {!erro && leis && leis.length > 0 && (
          <ul className="flex max-h-72 flex-col gap-1 overflow-y-auto">
            {leis.map((lei) => (
              <li
                key={lei}
                className="bg-muted/50 flex items-center gap-2 rounded-md px-3 py-2 text-sm"
              >
                <BookText className="text-muted-foreground size-4 shrink-0" aria-hidden />
                <span className="first-letter:uppercase">{lei}</span>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  )
}
