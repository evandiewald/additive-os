import AMProject from 0x4263f3e1effb2e48

pub fun main(account: Address) : [UInt64] {
    let projectOwner = getAccount(account)
    // log("NFT Owner")    
    let capability = projectOwner.getCapability<&{AMProject.ProjectOwner}>(/public/ProjectOwner)

    let receiverRef = capability.borrow()
        ?? panic("Could not borrow the receiver reference")

    return receiverRef.getIDs()
}