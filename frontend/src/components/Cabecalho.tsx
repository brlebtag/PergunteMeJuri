import { MoreVertical, Scale } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

interface Props {
  threadId: string | null
  onNovaSessao: () => void
  onVerLeis: () => void
}

export function Cabecalho({ threadId, onNovaSessao, onVerLeis }: Props) {
  return (
    <header className="flex items-center justify-between border-b px-4 py-3">
      <div className="flex items-center gap-2">
        <Scale className="size-5 text-primary" aria-hidden />
        <div>
          <h1 className="text-sm leading-tight font-semibold">PergunteMeJuri</h1>
          <p className="text-muted-foreground text-xs leading-tight">
            {threadId ? `Sessão ${threadId.slice(0, 8)}` : "Nenhuma sessão ativa"}
          </p>
        </div>
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button variant="ghost" size="icon" aria-label="Menu">
              <MoreVertical className="size-4" />
            </Button>
          }
        />
        <DropdownMenuContent align="end" className="w-60">
          <DropdownMenuGroup>
            <DropdownMenuLabel>Consulta</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onVerLeis}>Leis disponíveis</DropdownMenuItem>
          </DropdownMenuGroup>

          <DropdownMenuSeparator />

          <DropdownMenuGroup>
            <DropdownMenuLabel>Sessão</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onNovaSessao} disabled={!threadId}>
              Encerrar e iniciar nova
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <p className="text-muted-foreground px-2 py-1.5 text-xs">
            Apaga o histórico guardado neste navegador.
          </p>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  )
}
