import AMProject from 0x5cc83cb6d766bf4a

pub fun main(projectId: UInt64) : String {
    let projectOwner = getAccount(0x5cc83cb6d766bf4a)
    // log("NFT Owner")    
    let capability = projectOwner.getCapability<&{AMProject.ProjectOwner}>(/public/ProjectOwner)

    let receiverRef = capability.borrow()
        ?? panic("Could not borrow the receiver reference")

    return receiverRef.getMetadata(id: projectId)
}